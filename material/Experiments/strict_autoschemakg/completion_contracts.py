"""Frozen Lamport inputs and source-grounded completion contracts.

This module does not dispatch models or judge the truth of a candidate. Evidence
binding is deliberately downstream of the technical response classifier.
"""
from __future__ import annotations

from collections import defaultdict
from copy import deepcopy
import hashlib
import json
from pathlib import Path

from . import extended_artifacts as artifacts, recall_methods as methods
from . import reliability_v2 as reliability
from .contract import parse_json, sha256


ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "Experiments/data/corpus/Leslie Lamport.txt"
BASELINE = ROOT / ("Experiments/results/strict_autoschemakg/"
                   "local_lamport_recall_methods_v1/arms/baseline/extraction.jsonl")
SOURCE_HASH = "63380da5d92f6922fc57409643e4d624920981ea6f4b7642ab977bfaf787b7eb"
BASELINE_HASH = "1bebaf23997daccac6f033a68dc848a7ac75d9a4848ed8e368358da7328fb80f"
SOURCE_ID = "source:" + SOURCE_HASH[:16]
CATEGORIES = {"entity": "entity_relation_dict", "event": "event_entity_relation_dict",
              "relation": "event_relation_dict"}
PROTOCOL_ID = "source_grounded_completion_v1"


def _require(condition, message):
    if not condition:
        raise ValueError(message)


def _native_value(category, value):
    """Syntactic native triple/record check, with no semantic acceptance filter."""
    field_names = ("Event", "Entity") if category == "event" else ("Head", "Relation", "Tail")
    _require(isinstance(value, dict) and set(value) == set(field_names), "Invalid native value fields")
    for name in field_names:
        part = value[name]
        if name == "Entity":
            _require(isinstance(part, list) and all(isinstance(x, str) and x.strip() for x in part),
                     "Invalid event entity list")
        else:
            _require(isinstance(part, str) and bool(part.strip()), "Empty native value field")


def _endpoints(items, source_id):
    result = {}
    for item in items:
        fields = ("Event",) if item["category"] == "event" else (
            ("Head", "Tail") if item["category"] == "relation" else ())
        for field in fields:
            ident = f"{item['id']}:{field}"
            result[ident] = {"id": ident, "source_id": source_id, "text": item["value"][field],
                             "origin_item_id": item["origin_item_id"], "field": field,
                             "canonical_id": None}
    anchors = defaultdict(list)
    for entry in result.values():
        if entry["field"] == "Event":
            anchors[(entry["source_id"], entry["text"])].append(entry["id"])
    for entry in result.values():
        matches = anchors[(entry["source_id"], entry["text"])]
        if len(matches) == 1:
            entry["canonical_id"] = matches[0]
    return result


def load_inputs(source_path: Path = SOURCE, baseline_path: Path = BASELINE) -> dict:
    """Read exactly the frozen one-record baseline, preserving all native fields."""
    source_path, baseline_path = Path(source_path), Path(baseline_path)
    default = source_path == SOURCE and baseline_path == BASELINE
    if default:
        _require(sha256(SOURCE) == SOURCE_HASH, "Lamport source bytes changed")
        _require(sha256(BASELINE) == BASELINE_HASH, "Frozen extraction bytes changed")
    rows = [json.loads(line) for line in baseline_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    _require(len(rows) == 1, "Exactly one saved extraction is required")
    baseline = rows[0]
    source = source_path.read_text(encoding="utf-8-sig")
    _require(baseline["original_text"] == methods.normalize(source), "Baseline source differs")
    source_units = methods.source_units(source)
    source_hash = sha256(source_path)
    baseline_hash = sha256(baseline_path)
    source_id = "source:" + source_hash[:16]
    native = artifacts.inventory_extraction(baseline_path, "baseline" if default else source_id)
    items = [{"id": x["occurrence_id"], "category": x["category"],
              "value": deepcopy(x["value"]), "origin_item_id": x["occurrence_id"]}
             for x in native if x["category"] in CATEGORIES]
    counts = {"ee": len(baseline["entity_relation_dict"]),
              "ev_records": len(baseline["event_entity_relation_dict"]),
              "ev_links": sum(len(x["Entity"]) for x in baseline["event_entity_relation_dict"]),
              "vv": len(baseline["event_relation_dict"])}
    if default:
        _require(counts == {"ee": 9, "ev_records": 27, "ev_links": 101, "vv": 11},
                 "Frozen baseline cardinality changed")
    return {"source": source, "source_units": source_units, "baseline": baseline,
            "baseline_counts": counts, "items": items, "event_index": _endpoints(items, source_id),
            "source_id": source_id,
            "input_hashes": {"source": source_hash, "baseline": baseline_hash}}


def completion_requests(inputs: dict) -> list[dict]:
    """One source-and-graph-aware request for each native category."""
    baseline_items = deepcopy(inputs["items"])
    units = deepcopy(inputs["source_units"])
    requests = []
    for category in CATEGORIES:
        prompt = (
            "Find additional source-grounded native statements of category " + category + ". "
            "Use the full source and ALL existing entity, event and relation statements. "
            "Do not revise the baseline. Return candidates with native value fields, claim "
            "(direct or inferred), exact source_spans (unit_id, text, start, end with exclusive end), "
            "premise_refs (baseline item IDs or unit_id:start:end), and explanation. "
            "An empty candidates list is valid. Do not use external knowledge. "
            "Do not rank or truncate candidates. Return JSON only.\nSOURCE:\n"
            + inputs["source"] + "\nSOURCE_UNITS:\n" + json.dumps(units, ensure_ascii=False)
            + "\nBASELINE_ITEMS:\n" + json.dumps(baseline_items, ensure_ascii=False))
        requests.append({"request_id": f"completion:{category}", "kind": "completion",
                         "category": category, "item_ids": [x["id"] for x in baseline_items],
                         "baseline_items": baseline_items, "source_units": units,
                         "source_id": inputs.get("source_id", SOURCE_ID), "prompt": prompt,
                         "parameters": {"max_new_tokens": 4096}})
    return requests


def schema_for(request: dict) -> dict:
    _require(request.get("kind") == "completion" and request.get("category") in CATEGORIES,
             "Unknown completion request")
    string = {"type": "string", "minLength": 1}
    span = reliability.obj({"unit_id": string, "text": string,
                            "start": {"type": "number", "minimum": 0},
                            "end": {"type": "number", "minimum": 0}})
    candidate = reliability.obj({
        "value": reliability.triple_schema(request["category"]),
        "claim": {"type": "string", "enum": ["direct", "inferred"]},
        "source_spans": reliability.array(span),
        "premise_refs": reliability.array(string),
        "explanation": {"type": "string"}})
    return reliability.obj({"candidates": reliability.array(candidate)})


def classify(request: dict, raw: str) -> dict:
    """Retry only whole malformed answers, not missing or ambiguous evidence."""
    value = parse_json(raw)
    reliability.validate(value, schema_for(request))
    for candidate in value["candidates"]:
        _native_value(request["category"], candidate["value"])
        for span in candidate["source_spans"]:
            _require(type(span["start"]) is int and type(span["end"]) is int
                     and span["start"] < span["end"], "Span offsets require positive integer range")
        _require(all(ref.strip() for ref in candidate["premise_refs"]), "Empty premise reference")
    return value


def _span_binding(span, units):
    text = units.get(span["unit_id"])
    if text is None:
        return span, "unknown_source_unit"
    if (0 <= span["start"] < span["end"] <= len(text)
            and text[span["start"]:span["end"]] == span["text"]):
        return span, None
    first = text.find(span["text"])
    if first >= 0 and text.find(span["text"], first + 1) < 0:
        repaired = {**span, "start": first, "end": first + len(span["text"])}
        return repaired, "offset_repaired"
    return span, "ambiguous_or_missing_quote"


def _premise_binding(ref, known_ids, units):
    if ref in known_ids:
        return None
    parts = ref.rsplit(":", 2)
    if len(parts) == 3 and parts[0] in units:
        try:
            start, end = int(parts[1]), int(parts[2])
        except ValueError:
            return "unknown_premise"
        if 0 <= start < end <= len(units[parts[0]]):
            return None
    return "unknown_premise"


def _repaired_premises(original, repaired, refs, known_ids):
    """Only rewrite a quote-associated coordinate when every mapping agrees."""
    mapping = {}
    for old, new in zip(original, repaired):
        key = f"{old['unit_id']}:{old['start']}:{old['end']}"
        target = f"{new['unit_id']}:{new['start']}:{new['end']}"
        mapping.setdefault(key, set()).add(target)
    effective, repairs, findings = [], [], []
    for ref in refs:
        targets = mapping.get(ref, set()) if ref not in known_ids else set()
        if len(targets) > 1:
            findings.append("ambiguous_premise_offset_repair")
        new = next(iter(targets)) if len(targets) == 1 else ref
        effective.append(new)
        if new != ref:
            repairs.append({"original": ref, "effective": new})
    return effective, repairs, findings


def bind_candidates(inputs: dict, schedule: list[dict], results: list[dict], *, deterministic_repairs=False) -> dict:
    """Keep all validly parsed candidates, binding failures, and exact B+C union."""
    by_id = {x["request_id"]: x for x in results}
    _require(len(by_id) == len(results), "Duplicate completion result ID")
    units = {x["id"]: x["text"] for x in inputs["source_units"]}
    known_ids = {x["id"] for x in inputs["items"]}
    native_row = deepcopy(inputs["baseline"])
    seen = {category: {artifacts.digest(x) for x in native_row[field]}
            for category, field in CATEGORIES.items()}
    candidates, bindings, valid_count = [], [], 0
    for request in schedule:
        record = by_id.get(request["request_id"])
        if record is None or record.get("status") != "valid":
            continue
        valid_count += 1
        parsed = record["parsed"]
        _require(isinstance(parsed, dict) and isinstance(parsed.get("candidates"), list),
                 "Valid result lacks parsed candidates")
        category = request["category"]
        for index, candidate in enumerate(parsed["candidates"]):
            ident = f"{request['source_id']}:{request['request_id']}:{index:05d}"
            entry = {"id": ident, "category": category, "value": deepcopy(candidate["value"]),
                     "claim": candidate["claim"], "source_spans": deepcopy(candidate["source_spans"]),
                     "premise_refs": deepcopy(candidate["premise_refs"]),
                     "explanation": candidate["explanation"], "request_id": request["request_id"]}
            findings, repaired = [], []
            for span in candidate["source_spans"]:
                bound, issue = _span_binding(span, units)
                repaired.append(bound)
                if issue:
                    findings.append(issue)
            if not candidate["source_spans"]:
                findings.append("missing_source_span")
            effective_refs = candidate["premise_refs"]
            if deterministic_repairs:
                effective_refs, premise_repairs, premise_findings = _repaired_premises(
                    candidate["source_spans"], repaired, candidate["premise_refs"], known_ids)
                findings.extend(premise_findings)
                entry["original_candidate"] = deepcopy(candidate)
                entry["source_spans"] = deepcopy(repaired)
                entry["premise_refs"] = deepcopy(effective_refs)
            for ref in effective_refs:
                issue = _premise_binding(ref, known_ids, units)
                if issue:
                    findings.append(issue)
            if candidate["claim"] == "inferred" and not candidate["premise_refs"]:
                findings.append("missing_inference_premise")
            candidates.append(entry)
            bindings.append({"candidate_id": ident, "status": "finding" if any(
                issue != "offset_repaired" for issue in findings) else "bound",
                             "source_spans": repaired, "findings": findings})
            if deterministic_repairs:
                bindings[-1].update(premise_refs=deepcopy(effective_refs), premise_repairs=premise_repairs,
                                    original_premise_refs=deepcopy(candidate["premise_refs"]))
            fingerprint = artifacts.digest(candidate["value"])
            if fingerprint not in seen[category]:
                native_row[CATEGORIES[category]].append(deepcopy(candidate["value"]))
                seen[category].add(fingerprint)
    dependency_status = ("complete" if valid_count == len(schedule) else
                         "partial" if valid_count else "missing")
    return {"candidates": candidates, "bindings": bindings, "native_row": native_row,
            "dependency_status": dependency_status}
