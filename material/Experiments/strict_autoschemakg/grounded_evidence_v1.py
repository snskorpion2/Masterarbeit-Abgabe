"""Evidence IDs and source-fidelity gates. Binding is not semantic truth.

Only new opt-in runners import this module. Historical/native protocols stay
unchanged. No entity vocabulary, relation vocabulary, or language detector.
"""
from __future__ import annotations

from copy import deepcopy
import json
import re
from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError

from . import reliability_v2 as r
from .contract import parse_json

EVENT_PROVENANCE_KEY = "grounded_event_occurrence_provenance"


def catalog(source):
    """Nonempty paragraphs with offsets into the UNCHANGED original source."""
    if not isinstance(source, str) or not source.strip():
        raise ValueError("Nonempty source required")
    out = []
    for part in re.finditer(r"\S[\s\S]*?(?=\r?\n[ \t]*\r?\n|\Z)", source):
        end = part.end()
        while end > part.start() and source[end - 1].isspace():
            end -= 1
        out.append({"id": f"E{len(out)+1:04d}", "text": source[part.start():end],
                    "start": part.start(), "end": end})
    validate_catalog(out, source)
    return out


def validate_catalog(rows, source=None):
    ids = set()
    previous = 0
    for row in rows:
        if (set(row) != {"id", "text", "start", "end"} or not row["id"] or
                row["id"] in ids or not row["text"].strip() or
                type(row["start"]) is not int or type(row["end"]) is not int or
                row["start"] < previous or row["end"] <= row["start"] or
                row["end"] - row["start"] != len(row["text"])):
            raise ValueError("Invalid evidence catalog")
        if source is not None and (source[row["start"]:row["end"]] != row["text"] or
                                   source[previous:row["start"]].strip()):
            raise ValueError("Evidence catalog changed or omitted source text")
        ids.add(row["id"])
        previous = row["end"]
    if not ids or (source is not None and source[previous:].strip()):
        raise ValueError("Empty/incomplete catalog")
    return ids


def enum_array(ids, minimum=0):
    values = list(ids)
    return {"type": "array", "items": {"type": "string", "enum": values} if values else
            {"type": "string"}, "uniqueItems": True, "minItems": minimum,
            **({"maxItems": 0} if not values else {})}


def request(ident, prompt, schema, category="entity", parameters=None):
    return {"request_id": ident, "kind": "grounded_method_v1", "category": category,
            "prompt": prompt + "\nOUTPUT_CONTRACT (JSON only):\n" + json.dumps(schema, ensure_ascii=False),
            "output_schema": deepcopy(schema), "parameters": parameters or {"max_new_tokens": 4096}}


def schema_for(query):
    return query["output_schema"]


def classify(query, raw):
    result = parse_json(raw)
    try:
        Draft202012Validator(schema_for(query)).validate(result)
    except ValidationError as exc:
        raise ValueError("Grounded response violates its output schema") from exc
    if isinstance(result, dict) and isinstance(result.get("candidates"), list):
        from .completion_contracts import _native_value
        for candidate in result["candidates"]:
            if "value" in candidate:
                _native_value(query["category"], candidate["value"])
    return result


def candidate_schema(category, evidence, *, inferred=False):
    fields = {"value": r.triple_schema(category, missing=True), "evidence_ids": enum_array(sorted(validate_catalog(evidence)), 1)}
    if inferred:
        fields.update(claim={"type": "string", "enum": ["direct", "inferred"]},
                      explanation={"type": "string"})
    return r.obj(fields)


def assign_candidates(raw, category, prefix):
    return [{**deepcopy(row), "id": f"{prefix}:{i:04d}", "category": category}
            for i, row in enumerate(raw, 1)]


def verifier_request(candidates, evidence, ident):
    """Independent source check with one mandatory verdict per immutable ID."""
    known = validate_catalog(evidence)
    if not candidates or len({x["id"] for x in candidates}) != len(candidates):
        raise ValueError("Verifier requires nonempty unique candidates")
    verdict = r.obj({"status": {"type": "string", "enum": ["supported", "contradicted", "insufficient"]},
                     "evidence_ids": enum_array(sorted(known)), "reason": {"type": "string", "minLength": 1}})
    schema = r.obj({x["id"]: deepcopy(verdict) for x in candidates})
    prompt = (
        "Independently check each entire claim against the ORIGINAL source only. A source ID or matching "
        "words do not establish the relation. Check subject/object roles, direction, quantities, dates, "
        "negation, modality, and every participant. supported means the source entails the ENTIRE claim. "
        "contradicted means inconsistent with it; insufficient means not established or ambiguous. "
        "For an inferred claim require that the conclusion necessarily follows, not merely plausibility. "
        "Use any provided source evidence, preserve the source language. Never use memorized facts. "
        "Cite evidence IDs and briefly justify every verdict. Do not rewrite claims.\nCANDIDATES:\n"
        + json.dumps(candidates, ensure_ascii=False) + "\nORIGINAL_SOURCE:\n" + json.dumps(evidence, ensure_ascii=False))
    return request(ident, prompt, schema)


def gate(candidates, evidence, decisions):
    known = validate_catalog(evidence)
    if len({c["id"] for c in candidates}) != len(candidates):
        raise ValueError("Duplicate candidate IDs")
    if set(decisions) != {c["id"] for c in candidates}:
        raise ValueError("Incomplete source-verification decisions")
    accepted, audit = [], []
    for candidate in candidates:
        decision = decisions[candidate["id"]]
        refs = candidate.get("evidence_ids", [])
        bound = bool(refs) and len(refs) == len(set(refs)) and set(refs) <= known
        checked_refs = decision.get("evidence_ids", [])
        checked = bool(checked_refs) and set(checked_refs) <= known and bool(decision.get("reason", "").strip())
        status = decision.get("status")
        if status not in ("supported", "contradicted", "insufficient"):
            raise ValueError("Unknown verification status")
        keep = bound and checked and status == "supported"
        audit.append({"id": candidate["id"], "bound": bound, "verdict": deepcopy(decision),
                      "accepted": keep, "claim_limit": "model_verified_not_gold"})
        if keep:
            accepted.append({**deepcopy(candidate), "verification": deepcopy(decision)})
    return {"accepted": accepted, "audit": audit, "candidates": deepcopy(candidates)}


def event_occurrence_provenance(native_row):
    """Read occurrence metadata only when positions and native values still match."""
    metadata = native_row.get(EVENT_PROVENANCE_KEY)
    events = native_row.get("event_entity_relation_dict")
    if (not isinstance(metadata, dict) or set(metadata) != {"protocol", "records", "identity_claim"}
            or metadata["protocol"] != "occurrence_preserving_v2" or metadata["identity_claim"] is not False
            or not isinstance(metadata["records"], list) or not isinstance(events, list)
            or len(metadata["records"]) != len(events)):
        raise ValueError("Invalid event occurrence provenance")
    seen = set()
    fields = {"native_index", "occurrence_id", "origin", "candidate_id", "evidence_ids",
              "identity_status", "value_sha256"}
    for index, record in enumerate(metadata["records"]):
        if (not isinstance(record, dict) or set(record) != fields
                or type(record["native_index"]) is not int or record["native_index"] != index
                or not isinstance(record["occurrence_id"], str) or not record["occurrence_id"]
                or record["occurrence_id"] in seen or record["origin"] not in ("baseline", "accepted")
                or record["identity_status"] != "unresolved"
                or record["value_sha256"] != r.artifacts.digest(events[index])
                or not isinstance(record["evidence_ids"], list)
                or not all(isinstance(ref, str) and ref for ref in record["evidence_ids"])
                or len(record["evidence_ids"]) != len(set(record["evidence_ids"]))
                or (record["origin"] == "baseline" and record["candidate_id"] is not None)
                or (record["origin"] == "accepted"
                    and (not isinstance(record["candidate_id"], str) or not record["candidate_id"]))):
            raise ValueError("Invalid event occurrence provenance")
        seen.add(record["occurrence_id"])
    return deepcopy(metadata["records"])


def merge_native(baseline, accepted):
    """Preserve EV records, without inferring event identity from their labels.

    The native Event/Entity shape stays unchanged. Its separate occurrence
    index embedded in the native row binds each record to its evidence. Even
    identical values are not an event-identity decision. Baseline records
    retain their original grouping, which this merge does not verify.
    """
    from .completion_contracts import CATEGORIES, _native_value
    output, origins = deepcopy(baseline), {}
    baseline_hash = r.artifacts.digest(baseline)
    if EVENT_PROVENANCE_KEY in baseline:
        event_occurrences = event_occurrence_provenance(baseline)
    else:
        event_occurrences = [{"native_index": index, "origin": "baseline", "candidate_id": None,
                              "occurrence_id": "EV:" + r.artifacts.digest([baseline_hash, "baseline", index]),
                              "evidence_ids": [], "identity_status": "unresolved",
                              "value_sha256": r.artifacts.digest(value)}
                             for index, value in enumerate(output[CATEGORIES["event"]])]
    ids = [candidate["id"] for candidate in accepted]
    if len(ids) != len(set(ids)):
        raise ValueError("Duplicate candidate IDs in occurrence-preserving merge")
    for candidate in accepted:
        category, value = candidate["category"], candidate["value"]
        _native_value(category, value)
        key = category + ":" + r.artifacts.digest(value)
        origins.setdefault(key, []).append(candidate["id"])
        target = output[CATEGORIES[category]]
        if category == "event":
            event_occurrences.append({"native_index": len(target), "origin": "accepted",
                                      "candidate_id": candidate["id"],
                                      "occurrence_id": "EV:" + r.artifacts.digest([baseline_hash, len(target), candidate["id"]]),
                                      "evidence_ids": deepcopy(candidate.get("evidence_ids", [])),
                                      "identity_status": "unresolved",
                                      "value_sha256": r.artifacts.digest(value)})
            target.append(deepcopy(value))
        elif value not in target:
            target.append(deepcopy(value))
    output[EVENT_PROVENANCE_KEY] = {"protocol": "occurrence_preserving_v2",
                                    "records": deepcopy(event_occurrences), "identity_claim": False}
    event_occurrence_provenance(output)
    return {"native_row": output, "provenance": origins,
            "event_occurrences": event_occurrences,
            "merge_protocol": "occurrence_preserving_v2",
            "event_identity_claim": False}
