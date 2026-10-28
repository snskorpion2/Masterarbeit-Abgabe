"""Conservative temporal projection of existing native triples.

The model proposes formalizations, but this module only binds them to input
occurrences. Neither a bound span nor a primitive certifies source truth.
"""
from __future__ import annotations

from calendar import monthrange
from copy import deepcopy
from datetime import date
import hashlib
import json
import re

from .contract import parse_json
from . import reliability_v2 as reliability


_MONTHS = {name.lower(): number for number, name in enumerate(
    ("January", "February", "March", "April", "May", "June", "July",
     "August", "September", "October", "November", "December"), 1)}
_MONTH_PATTERN = "|".join(_MONTHS)


def _require(condition, message):
    if not condition:
        raise ValueError(message)


def formalization_requests(items: list[dict], event_index: dict, *, contract_version="v1") -> list[dict]:
    """Partition occurrence inputs; never include a source article."""
    _require(contract_version in ("v1", "v2"), "Unknown temporal contract version")
    ids = [item["id"] for item in items]
    _require(len(ids) == len(set(ids)), "Duplicate input occurrence ID")
    requests = []
    for offset in range(0, len(items), 8):
        batch = []
        for item in items[offset:offset + 8]:
            fields = ("Event", "Entity") if item["category"] == "event" else ("Head", "Relation", "Tail")
            batch.append({"id": item["id"], "category": item["category"],
                          "value": {field: deepcopy(item["value"][field]) for field in fields},
                          "origin_item_id": item["origin_item_id"]})
        allowed_index_fields = ("id", "source_id", "text", "origin_item_id", "field", "canonical_id")
        subset = {key: {field: deepcopy(value[field]) for field in allowed_index_fields}
                  for key, value in event_index.items()
                  if any(value.get("origin_item_id") == item["origin_item_id"] for item in batch)}
        prompt = (
            "Formalize only explicitly supported temporal assertions in these native input "
            "triples. Do not use an article, external facts, aliases, inferred roles, or "
            "invented events. Return an items object keyed by every input item ID exactly once, "
            "without extra keys. Each value has status (formalized/unformalized), atoms, reason. Uncertain, negated, "
            "hypothetical, named-year and non-temporal claims are unformalized. An atom "
            "has kind (event_time/before/after), source_item_id, role, polarity, "
            "input_spans (field,start,end,text); event_time also has event_id, literal, "
            "precision (year/month/day/range); before/after has head_event_id and "
            "tail_event_id. Spans use Unicode codepoint offsets, exclusive end. Event IDs "
            "must come from EVENT_INDEX. Return JSON only.\nITEMS:\n"
            + json.dumps(batch, ensure_ascii=False, sort_keys=True)
            + "\nEVENT_INDEX:\n" + json.dumps(subset, ensure_ascii=False, sort_keys=True))
        if contract_version == "v2":
            prompt = _v2_prompt(batch, subset)
        request = {"request_id": f"temporal:{offset // 8:05d}", "kind": "temporal",
                         "item_ids": [item["id"] for item in batch], "items": batch,
                         "event_index": subset, "prompt": prompt,
                         "parameters": {"max_new_tokens": 4096}}
        if contract_version == "v2":
            request["contract_version"] = "v2"
        requests.append(request)
    return requests


def _v2_prompt(batch, subset):
    example_input = {"id": "example-event", "category": "event",
                     "value": {"Event": "Opened in 2001", "Entity": []}}
    example_output = {"items": {"example-event": {"status": "formalized", "atoms": [{
        "kind": "event_time", "source_item_id": "example-event", "role": "event_time",
        "polarity": "positive", "event_id": "example-event:Event", "literal": "2001",
        "precision": "year", "input_spans": [{"field": "Event", "start": 10,
                                                 "end": 14, "text": "2001"}]}], "reason": ""}}}
    return (
        "Temporal formalization contract v2. Use only ITEMS and EVENT_INDEX, not an article, "
        "external facts, invented events, or inferred relations. Return JSON only: an items object "
        "with every input ID exactly once and no other keys. Each entry has status "
        "(formalized or unformalized), atoms (array), and reason (string). Use unformalized "
        "with atoms=[] for negated, hypothetical, uncertain, non-temporal, unsupported, or "
        "named-year claims. Do not turn absence of evidence into a positive assertion.\n"
        "Grammar: event_time := {kind:'event_time',source_item_id,role:'event_time',"
        "polarity:'positive',input_spans,event_id,literal,precision}. before/after := "
        "{kind:'before'|'after',source_item_id,role:'temporal',polarity:'positive',"
        "input_spans,head_event_id,tail_event_id}. Use exactly the IDs for the current input item. "
        "event_time is the time of the Event, not any year mentioned in its title or name. "
        "literal is the verbatim date expression in Event. precision is year, month, day, or "
        "range matching that literal. A complete explicit interval such as 'from 2001 to 2003' "
        "is one range atom, not two year atoms. before/after requires the matching Relation "
        "value and the two prescribed endpoint IDs.\n"
        "Every atom needs input_spans with at least one exact quote. A span is "
        "{field,start,end,text}: field names one existing string field of that same ITEMS entry, "
        "text is a verbatim substring of that field value, start/end are Unicode codepoint "
        "offsets within that value, start inclusive and end exclusive. event_time needs its "
        "own Event span whose text equals literal; before/after needs its own Relation span "
        "whose text expresses before or after. Never cite a different field, item, or article.\n"
        "Independent synthetic format example, not an article and not a task answer: input "
        + json.dumps(example_input, ensure_ascii=False, sort_keys=True)
        + " with EVENT_INDEX key 'example-event:Event' yields "
        + json.dumps(example_output, ensure_ascii=False, sort_keys=True)
        + ". The example illustrates syntax only.\nITEMS:\n"
        + json.dumps(batch, ensure_ascii=False, sort_keys=True)
        + "\nEVENT_INDEX:\n" + json.dumps(subset, ensure_ascii=False, sort_keys=True))


def schema_for(request: dict) -> dict:
    _require(request.get("kind") == "temporal", "Unknown temporal request")
    version = request.get("contract_version", "v1")
    _require(version in ("v1", "v2"), "Unknown temporal contract version")
    if version == "v2":
        return _schema_v2(request)
    string = {"type": "string"}
    nonempty = {"type": "string", "minLength": 1}
    span = reliability.obj({"field": nonempty, "start": {"type": "number", "minimum": 0},
                            "end": {"type": "number", "minimum": 0}, "text": nonempty})
    atom = {"type": "object", "properties": {
        "kind": {"type": "string", "enum": ["event_time", "before", "after"]},
        "source_item_id": nonempty, "role": nonempty, "polarity": nonempty,
        "input_spans": reliability.array(span), "event_id": nonempty,
        "head_event_id": nonempty, "tail_event_id": nonempty,
        "literal": nonempty, "precision": nonempty},
        "required": ["kind", "source_item_id", "role", "polarity", "input_spans"],
        "additionalProperties": False}
    entry = reliability.obj({"status": {"type": "string", "enum": ["formalized", "unformalized"]},
                             "atoms": reliability.array(atom), "reason": string})
    return reliability.obj({"items": reliability.obj({item_id: entry for item_id in request["item_ids"]})})


def _schema_v2(request):
    nonempty = {"type": "string", "minLength": 1}
    entries = {}
    for item in request["items"]:
        item_id = item["id"]
        fields = (["Event"] if item["category"] == "event" else
                  ["Relation"] if item["category"] == "relation" else
                  [name for name, value in item["value"].items() if isinstance(value, str)])
        span = reliability.obj({"field": {"type": "string", "enum": fields},
                                "start": {"type": "integer", "minimum": 0},
                                "end": {"type": "integer", "minimum": 0}, "text": nonempty})
        spans = reliability.array(span)
        spans["minItems"] = 1
        common = {"source_item_id": {"type": "string", "enum": [item_id]},
                  "polarity": {"type": "string", "enum": ["positive"]},
                  "input_spans": spans}
        atom_schema = {"type": "string"}
        if item["category"] == "event":
            endpoint_id = f"{item_id}:Event"
            if endpoint_id in request["event_index"]:
                atom_schema = reliability.obj({"kind": {"type": "string", "enum": ["event_time"]},
                    **common, "role": {"type": "string", "enum": ["event_time"]},
                    "event_id": {"type": "string", "enum": [endpoint_id]},
                    "literal": nonempty,
                    "precision": {"type": "string", "enum": ["year", "month", "day", "range"]}})
        elif item["category"] == "relation":
            head, tail = f"{item_id}:Head", f"{item_id}:Tail"
            if head in request["event_index"] and tail in request["event_index"]:
                atom_schema = reliability.obj({"kind": {"type": "string", "enum": ["before", "after"]},
                    **common, "role": {"type": "string", "enum": ["temporal"]},
                    "head_event_id": {"type": "string", "enum": [head]},
                    "tail_event_id": {"type": "string", "enum": [tail]}})
        atoms = reliability.array(atom_schema)
        if atom_schema == {"type": "string"}:
            atoms["maxItems"] = 0
        entries[item_id] = reliability.obj({"status": {"type": "string", "enum": ["formalized", "unformalized"]},
                                            "atoms": atoms, "reason": {"type": "string"}})
    return reliability.obj({"items": reliability.obj(entries)})


def classify(request: dict, raw: str) -> dict:
    """Retry malformed wire contracts, not binding or semantic findings."""
    if request.get("contract_version", "v1") == "v2":
        import jsonschema
        value = parse_json(raw)
        try:
            jsonschema.validate(value, schema_for(request))
        except jsonschema.ValidationError as exc:
            raise ValueError("Invalid temporal v2 response") from exc
        for entry in value["items"].values():
            for atom in entry["atoms"]:
                for span in atom["input_spans"]:
                    _require(type(span["start"]) is int and type(span["end"]) is int
                             and span["start"] < span["end"], "Invalid span offsets")
                if atom["kind"] == "event_time":
                    _require(any(span["field"] == "Event" and span["text"] == atom["literal"]
                                 for span in atom["input_spans"]), "Missing event date literal span")
        return {"items": [{"item_id": item_id, **value["items"][item_id]}
                          for item_id in request["item_ids"]]}
    value = parse_json(raw)
    schema = schema_for(request)
    _require(isinstance(value, dict) and set(value) == {"items"} and isinstance(value["items"], dict), "Invalid temporal response")
    _require(set(value["items"]) == set(request["item_ids"]), "Missing or extra formalization item ID")
    entry_schema = schema["properties"]["items"]["properties"][request["item_ids"][0]] if request["item_ids"] else None
    for entry in value["items"].values():
        _require(isinstance(entry, dict) and set(entry) == set(entry_schema["required"]), "Invalid formalization entry")
        _require(entry["status"] in ("formalized", "unformalized"), "Invalid formalization status")
        _require(isinstance(entry["atoms"], list) and isinstance(entry["reason"], str), "Invalid formalization fields")
        for atom in entry["atoms"]:
            _require(isinstance(atom, dict) and set(atom).issubset(entry_schema["properties"]["atoms"]["items"]["properties"]), "Invalid atom fields")
            common = {"kind", "source_item_id", "role", "polarity", "input_spans"}
            _require(common.issubset(atom) and atom["kind"] in ("event_time", "before", "after"), "Invalid atom core")
            _require(all(isinstance(atom[key], str) and atom[key] for key in common - {"input_spans"}), "Invalid atom strings")
            _require(isinstance(atom["input_spans"], list), "Invalid atom spans")
            for key in (("event_id", "literal", "precision") if atom["kind"] == "event_time" else ("head_event_id", "tail_event_id")):
                _require(key in atom and isinstance(atom[key], str) and atom[key], "Missing atom identifier or literal")
            for span in atom["input_spans"]:
                _require(isinstance(span, dict) and set(span) == {"field", "start", "end", "text"}, "Invalid span fields")
                _require(isinstance(span["field"], str) and span["field"] and isinstance(span["text"], str) and span["text"], "Invalid span text")
                _require(type(span["start"]) is int and type(span["end"]) is int
                         and 0 <= span["start"] < span["end"], "Invalid span offsets")
    return {"items": [{"item_id": item_id, **value["items"][item_id]}
                      for item_id in request["item_ids"]]}


def _date_bounds(literal: str, precision: str):
    """Return conservative bounds, or None for unsupported/invalid forms."""
    literal = literal.strip()
    if precision == "range":
        match = re.fullmatch(r"(?:from\s+)?(.+?)\s+(?:to|through|until|–|—)\s+(.+)", literal, re.I)
        if not match:
            return None
        left = _single_date(match.group(1).strip())
        right = _single_date(match.group(2).strip())
        if left and right and left[0] <= right[1]:
            return left[0], right[1]
        return None
    bounds = _single_date(literal)
    return bounds[:2] if bounds and bounds[2] == precision else None


def _single_date(literal: str):
    try:
        if re.fullmatch(r"\d{4}", literal):
            year = int(literal)
            return date(year, 1, 1).isoformat(), date(year, 12, 31).isoformat(), "year"
        if re.fullmatch(r"\d{4}-\d{2}", literal):
            year, month = map(int, literal.split("-"))
            return date(year, month, 1).isoformat(), date(year, month, monthrange(year, month)[1]).isoformat(), "month"
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", literal):
            day = date.fromisoformat(literal).isoformat()
            return day, day, "day"
        match = re.fullmatch(rf"({_MONTH_PATTERN})\s+(\d{{1,2}}),?\s+(\d{{4}})", literal, re.I)
        if match:
            day = date(int(match.group(3)), _MONTHS[match.group(1).lower()], int(match.group(2))).isoformat()
            return day, day, "day"
        match = re.fullmatch(rf"({_MONTH_PATTERN})\s+(\d{{4}})", literal, re.I)
        if match:
            year, month = int(match.group(2)), _MONTHS[match.group(1).lower()]
            return date(year, month, 1).isoformat(), date(year, month, monthrange(year, month)[1]).isoformat(), "month"
    except (ValueError, OverflowError):
        return None
    return None


def _non_asserted(text):
    return isinstance(text, str) and (
        re.search(r"\b(?:not|never|if|perhaps|possibly)\b", text, re.I)
        or re.search(r"\b(?:may|might|could|would)\s+[a-z]+\b", text, re.I))


def _binding(atom, item, event_index):
    issues = []
    value = item["value"]
    spans = atom.get("input_spans", [])
    if atom.get("source_item_id") != item["id"]:
        issues.append("wrong_source_item")
    if not spans:
        issues.append("missing_input_span")
    for span in spans:
        field = span["field"]
        if (field not in value or not isinstance(value[field], str)
                or not 0 <= span["start"] < span["end"] <= len(value[field])
                or value[field][span["start"]:span["end"]] != span["text"]):
            issues.append("unbound_input_span")
    if atom.get("polarity") != "positive":
        issues.append("non_positive")
    kind = atom["kind"]
    if kind == "event_time":
        event_text = value.get("Event", "")
        if _non_asserted(event_text):
            issues.append("explicitly_non_asserted_event")
        endpoint = event_index.get(atom.get("event_id"))
        if (item["category"] != "event" or endpoint is None or
                endpoint.get("id") != atom.get("event_id") or
                endpoint.get("origin_item_id") != item.get("origin_item_id") or
                endpoint.get("field") != "Event" or endpoint.get("text") != value.get("Event")):
            issues.append("unknown_or_unbound_event")
        if atom.get("role") != "event_time" or not any(s["field"] == "Event" and s["text"] == atom.get("literal") for s in spans):
            issues.append("unsupported_date_role_or_literal")
        bounds = _date_bounds(atom.get("literal", ""), atom.get("precision", ""))
        if bounds is None:
            issues.append("unsupported_or_invalid_date")
        # A leading year in an award/title name is not an event date.
        name_years = re.finditer(
            r"\b(\d{4})\s+(?:(?:\w+\s+){0,3})(?:award|prize|medal|book|manual|title)\b",
            event_text, re.I)
        if any(s["field"] == "Event" and s["text"] == atom.get("literal")
               and s["start"] < match.end(1) and match.start(1) < s["end"]
               for match in name_years for s in spans):
            issues.append("date_in_name")
        if issues:
            return None, sorted(set(issues))
        return {"kind": "event_time", "event_id": endpoint.get("canonical_id") or endpoint["id"],
                "endpoint_occurrence_ids": [atom["event_id"]],
                "earliest_start": bounds[0], "latest_end": bounds[1],
                "date_role": atom["role"], "literal": atom["literal"], "precision": atom["precision"]}, []
    if kind in ("before", "after"):
        if any(_non_asserted(value.get(field, "")) for field in ("Head", "Tail")):
            issues.append("explicitly_non_asserted_event")
        head = event_index.get(atom.get("head_event_id"))
        tail = event_index.get(atom.get("tail_event_id"))
        if item["category"] != "relation" or atom.get("role") != "temporal":
            issues.append("non_temporal_relation")
        if (not head or not tail or head.get("id") != f"{item['id']}:Head"
                or tail.get("id") != f"{item['id']}:Tail"):
            issues.append("unknown_or_same_endpoint")
        else:
            if head.get("text") != value.get("Head") or tail.get("text") != value.get("Tail"):
                issues.append("unbound_relation_endpoint")
            if head.get("source_id") != tail.get("source_id"):
                issues.append("cross_source_relation")
        if value.get("Relation", "").strip().lower() != kind or not any(s["field"] == "Relation" and s["text"].strip().lower() == kind for s in spans):
            issues.append("unsupported_relation_text")
        if issues:
            return None, sorted(set(issues))
        return {"kind": kind, "head": head.get("canonical_id") or head["id"],
                "tail": tail.get("canonical_id") or tail["id"],
                "endpoint_occurrence_ids": [atom["head_event_id"], atom["tail_event_id"]]}, []
    return None, ["unknown_atom_kind"]


def _repair_atom_spans(atom, item):
    repaired = deepcopy(atom)
    repairs = []
    for index, span in enumerate(repaired.get("input_spans", [])):
        field_text = item["value"].get(span["field"])
        if not isinstance(field_text, str):
            continue
        if (0 <= span["start"] < span["end"] <= len(field_text)
                and field_text[span["start"]:span["end"]] == span["text"]):
            continue
        first = field_text.find(span["text"])
        if first < 0 or field_text.find(span["text"], first + 1) >= 0:
            continue
        old_start, old_end = span["start"], span["end"]
        span["start"], span["end"] = first, first + len(span["text"])
        repairs.append({"span_index": index, "old_start": old_start, "old_end": old_end,
                        "new_start": span["start"], "new_end": span["end"]})
    return repaired, repairs


def project_primitives(schedule: list[dict], results: list[dict], event_index: dict, *, repair_spans=False,
                       deterministic_repairs=False) -> dict:
    """Bind valid suggestions; preserve invalid semantics without retrying."""
    by_id = {record["request_id"]: record for record in results}
    _require(len(by_id) == len(results), "Duplicate temporal result ID")
    primitives, unformalized, invalid = [], [], []
    seen_primitive_ids = set()
    valid_count = 0
    span_repairs = []
    precision_repairs = []
    for request in schedule:
        record = by_id.get(request["request_id"])
        if record is None or record.get("status") != "valid":
            continue
        valid_count += 1
        parsed = record["parsed"]
        items = {item["id"]: item for item in request["items"]}
        for entry in parsed["items"]:
            item = items.get(entry["item_id"])
            if item is None:
                invalid.append({"request_id": request["request_id"], "item_id": entry["item_id"], "findings": ["unknown_item_id"]})
                continue
            if entry["status"] == "unformalized":
                unformalized.append({"item_id": entry["item_id"], "reason": entry["reason"]})
                if entry["atoms"]:
                    invalid.append({"item_id": entry["item_id"], "findings": ["atoms_on_unformalized_item"]})
                continue
            if not entry["atoms"]:
                unformalized.append({"item_id": entry["item_id"], "reason": "no_atoms"})
            for ordinal, atom in enumerate(entry["atoms"]):
                original_atom = deepcopy(atom)
                if repair_spans:
                    atom, repairs = _repair_atom_spans(atom, item)
                    span_repairs.extend({"item_id": item["id"], "atom_index": ordinal, **repair}
                                        for repair in repairs)
                precision_repair = None
                if deterministic_repairs and atom.get("kind") == "event_time":
                    literal = atom.get("literal", "")
                    single = _single_date(literal.strip())
                    inferred = single[2] if single else "range" if _date_bounds(literal, "range") else None
                    if inferred and inferred != atom.get("precision"):
                        atom = {**atom, "precision": inferred}
                        precision_repair = {"item_id": item["id"], "atom_index": ordinal,
                                            "original_atom": original_atom, "effective_atom": deepcopy(atom)}
                primitive, issues = _binding(atom, item, event_index)
                if precision_repair is not None:
                    precision_repair["binding_findings"] = issues
                    precision_repair["accepted"] = not issues
                    precision_repairs.append(precision_repair)
                if issues:
                    invalid.append({"item_id": entry["item_id"], "atom_index": ordinal, "findings": issues})
                    unformalized.append({"item_id": entry["item_id"], "atom_index": ordinal,
                                         "reason": ",".join(issues)})
                    continue
                stable = json.dumps({"item_id": item["id"], "atom": primitive,
                                     "spans": atom["input_spans"]}, sort_keys=True, ensure_ascii=False)
                primitive["id"] = "temporal:" + hashlib.sha256(stable.encode("utf-8")).hexdigest()[:20]
                if primitive["id"] in seen_primitive_ids:
                    invalid.append({"item_id": entry["item_id"], "atom_index": ordinal,
                                    "findings": ["duplicate_atom"]})
                    continue
                seen_primitive_ids.add(primitive["id"])
                primitive["source_item_ids"] = [item["id"]]
                primitive["input_spans"] = deepcopy(atom["input_spans"])
                primitive["source_id"] = event_index[primitive.get("event_id", primitive.get("head"))]["source_id"]
                primitives.append(primitive)
    status = "complete" if valid_count == len(schedule) else "partial" if valid_count else "missing"
    projection = {"primitives": primitives, "unformalized": unformalized,
                  "invalid_bindings": invalid, "dependency_status": status}
    if repair_spans:
        projection["span_repairs"] = span_repairs
    if deterministic_repairs:
        projection["precision_repairs"] = precision_repairs
    return projection
