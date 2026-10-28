"""Lossless, opt-in bridge for exact duplicate judge-set members."""
from copy import deepcopy
import json

from .contract import parse_json

PROTOCOL = "exact_judge_set_duplicates_v1"


def prepare(request, raw):
    """Return effective JSON text and a separate audit, or unchanged text and None."""
    if request.get("judge_set_protocol") != PROTOCOL or request.get("kind") not in ("more", "incorrect"):
        raise ValueError("Unknown judge set bridge contract")
    from . import reliability_v2 as reliability
    value = parse_json(raw)
    schema = deepcopy(reliability.schema_for(request))
    field = "incorrect_ids" if request["kind"] == "incorrect" else "missing"
    spec = schema["properties"][field]
    spec.pop("uniqueItems", None)
    if field == "incorrect_ids":
        spec.pop("maxItems", None)
    elif request["category"] == "event":
        spec["items"]["properties"]["Entity"].pop("uniqueItems", None)
    reliability.validate(value, schema)

    duplicates = []
    if field == "incorrect_ids":
        first = {}
        kept = []
        for index, ident in enumerate(value[field]):
            if ident in first:
                duplicates.append({"duplicate_index": index, "first_index": first[ident]})
            else:
                first[ident] = index
                kept.append(ident)
    elif request["category"] == "event":
        first = {}
        kept = []
        for index, record in enumerate(value[field]):
            entities = []
            for member_index, entity in enumerate(record["Entity"]):
                key = (record["Event"], entity)
                if key in first:
                    duplicates.append({"duplicate_index": [index, member_index],
                                       "first_index": list(first[key])})
                else:
                    first[key] = (index, member_index)
                    entities.append(entity)
            if entities:
                kept.append({**record, "Entity": entities})
    else:
        first = {}
        kept = []
        for index, record in enumerate(value[field]):
            key = (record["Head"], record["Relation"], record["Tail"])
            if key in first:
                duplicates.append({"duplicate_index": index, "first_index": first[key]})
            else:
                first[key] = index
                kept.append(record)
    if not duplicates:
        return raw, None
    effective = {field: kept}
    raw_units = (sum(len(record["Entity"]) for record in value[field])
                 if field == "missing" and request["category"] == "event" else len(value[field]))
    effective_units = (sum(len(record["Entity"]) for record in kept)
                       if field == "missing" and request["category"] == "event" else len(kept))
    effective_text = json.dumps(effective, ensure_ascii=False, allow_nan=False)
    count_kind = "id" if field == "incorrect_ids" else "record"
    audit = {"protocol": PROTOCOL, "field": field,
             f"raw_{count_kind}_count": len(value[field]),
             f"effective_{count_kind}_count": len(kept),
             "raw_unit_count": raw_units, "effective_unit_count": effective_units,
             "duplicate_count": len(duplicates), "duplicates": duplicates,
             "effective_json": effective_text}
    return effective_text, audit
