"""Opt-in exact native missing-set subtraction, after exact duplicate repair."""
from contextlib import contextmanager
from contextvars import ContextVar
from copy import deepcopy
import json

from .contract import parse_json

PROTOCOL = "exact_native_missing_difference_v1"
CONFIDENCE_PROTOCOL = "effective_judge_answer_confidence_v1"
_ACTIVE = ContextVar("exact_missing_repair", default=False)


@contextmanager
def scope(enabled=False):
    token = _ACTIVE.set(bool(enabled))
    try:
        yield
    finally:
        _ACTIVE.reset(token)


def enabled():
    return _ACTIVE.get()


def prepare(request, effective):
    from . import reliability_v2 as r, technical_repairs as repairs, judge_set_bridge
    if (request.get("kind") != "more" or request.get("exact_missing_protocol") != PROTOCOL
            or request.get("judge_set_protocol") != judge_set_bridge.PROTOCOL
            or request.get("missing_consistency_protocol") != repairs.MISSING_PROTOCOL):
        raise ValueError("Unknown exact missing-set contract")
    # Validate every input field before subtraction. An invalid field must never
    # become valid merely because its containing statement would be removed.
    validation_request = deepcopy(request)
    validation_request.pop("missing_consistency_protocol")
    value = r.classify(validation_request, effective)
    size = 2 if request["category"] == "event" else 3
    units = request["existing_native_units"]
    if (not isinstance(units, list) or any(not isinstance(unit, (list, tuple)) or len(unit) != size
            or any(not isinstance(field, str) or not field.strip() for field in unit) for unit in units)):
        raise ValueError("Invalid native-unit provenance")
    existing = {tuple(unit) for unit in units}
    kept, removed = [], []
    for record in value["missing"]:
        if size == 2:
            entities = []
            for entity in record["Entity"]:
                key = (record["Event"], entity)
                if key in existing:
                    removed.append(list(key))
                else:
                    entities.append(entity)
            if entities:
                kept.append({**record, "Entity": entities})
        else:
            key = tuple(record[field] for field in ("Head", "Relation", "Tail"))
            if key in existing:
                removed.append(list(key))
            else:
                kept.append(record)
    text = json.dumps({"missing": kept}, ensure_ascii=False, allow_nan=False) if removed else effective
    return text, {"protocol": PROTOCOL, "removed_units": removed, "removed_count": len(removed),
                  "effective_json": text, "comparison": "character_exact_no_normalization"}


def confidence_result(result):
    """Use effective verdict only when different; preserve identical old requests."""
    effective = result.get("effective_response", result.get("raw_response"))
    changed = effective != result.get("raw_response")
    return effective, changed
