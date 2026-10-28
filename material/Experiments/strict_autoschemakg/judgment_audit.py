"""Conservative, offline structural audit of original six-stage triple-judge calls.

This does not validate a model's semantic judgment or replace native results.
"""

import ast
from collections import Counter, defaultdict, deque
import json
import re


_STAGES = (("entity", "more"), ("event_entity", "more"), ("relation", "more"),
           ("entity", "incorrect"), ("event_entity", "incorrect"),
           ("relation", "incorrect"))
_CATEGORY = {"entity": "entity", "event_entity_link": "event_entity", "relation": "relation"}
_FIELDS = {"entity": ("Head", "Relation", "Tail"),
           "event_entity": ("Event", "Entity"),
           "relation": ("Head", "Relation", "Tail")}
_PROMPT_MARKERS = (
    "The given entity relationship recognition results as follows:",
    "The given entity recognition results as followed:",
    "The given event relationship recognition results as followed:",
    "The model entity relationship recognition results as follows:",
    "The model named entity recognition results as followed:",
    "The model event relationship recognition results as followed:",
)
_PROMPT_CATEGORIES = ("entity", "event", "relation", "entity", "event", "relation")
_SOURCE_MARKER = "The text paragraphs are provided as followed:"


class _DuplicateKey(ValueError):
    pass


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise _DuplicateKey("duplicate_key")
        result[key] = value
    return result


def _check_ast_keys(node):
    for child in ast.walk(node):
        if isinstance(child, ast.Dict):
            seen = set()
            for key in child.keys:
                if not isinstance(key, ast.Constant) or not isinstance(key.value, str):
                    raise ValueError("invalid_key")
                if key.value in seen:
                    raise _DuplicateKey("duplicate_key")
                seen.add(key.value)


def _objects(raw, kind):
    if not isinstance(raw, str) or not raw.strip():
        raise ValueError("empty_response")
    value = raw.strip()
    sentinel = "All recognized!" if kind == "more" else "all correct!"
    if value.casefold() == sentinel.casefold():
        return [], True
    try:
        parsed = json.loads(value, object_pairs_hook=_pairs,
                            parse_constant=lambda _: (_ for _ in ()).throw(ValueError("invalid_constant")))
    except _DuplicateKey:
        raise
    except (ValueError, TypeError):
        try:
            tree = ast.parse(value, mode="exec")
            if not tree.body or any(not isinstance(stmt, ast.Expr) for stmt in tree.body):
                raise ValueError("invalid_literal")
            _check_ast_keys(tree)
            parsed = []
            for stmt in tree.body:
                part = ast.literal_eval(stmt.value)
                if isinstance(part, tuple):
                    parsed.extend(part)
                else:
                    parsed.append(part)
            if len(parsed) == 1:
                parsed = parsed[0]
        except _DuplicateKey:
            raise
        except (SyntaxError, ValueError, TypeError, MemoryError, RecursionError) as exc:
            raise ValueError("invalid_literal") from exc
    if isinstance(parsed, dict):
        parsed = [parsed]
    elif isinstance(parsed, (list, tuple)):
        parsed = list(parsed)
    else:
        raise ValueError("invalid_structure")
    if not parsed or any(not isinstance(obj, dict) for obj in parsed):
        raise ValueError("invalid_structure")
    return parsed, False


def _units(obj, category):
    if set(obj) != set(_FIELDS[category]):
        raise ValueError("invalid_fields")
    if category == "event_entity":
        if not isinstance(obj["Event"], str) or not obj["Event"]:
            raise ValueError("invalid_fields")
        entities = obj["Entity"]
        if not isinstance(entities, list) or not all(isinstance(x, str) and x for x in entities):
            raise ValueError("invalid_fields")
        if not entities:
            raise ValueError("empty_entity_list")
        return [(obj["Event"], entity) for entity in entities]
    fields = _FIELDS[category]
    if not all(isinstance(obj[field], str) and obj[field] for field in fields):
        raise ValueError("invalid_fields")
    return [tuple(obj[field] for field in fields)]


def _native_count(raw, category, kind):
    """Replicate original parser counts for comparison, never as validity proof."""
    if not isinstance(raw, str):
        return None
    stripped = "\n".join(line for line in raw.split("\n") if line.strip())
    marker = "All recognized" if kind == "more" else "all correct"
    if marker in stripped:
        return 0
    if category != "event_entity":
        return len(stripped.split("\n"))
    count = 0
    for line in stripped.split("\n"):
        match = re.search(r"\[(.*?)\]", line)
        if match:
            count += len(match.group().strip("[]").split("', '"))
    return count


def _metric(n, wrong, more):
    if n == 0 or n <= wrong:
        return {"precision": None, "recall": None, "f1": None}
    precision = round((n - wrong) / n, 4)
    recall = round((n - wrong) / (n - wrong + more), 4)
    return {"precision": precision, "recall": recall,
            "f1": round(2 * precision * recall / (precision + recall), 4)}


def _verify_schedule(calls, inventory):
    if not calls or len(calls) % 6:
        return ["incomplete_six_stage_schedule"]
    record = inventory.get("native_context_record", {})
    passage = record.get("passage")
    if not isinstance(passage, str) or not passage:
        return ["missing_inventory_passage"]
    expected = {}
    for category in set(_PROMPT_CATEGORIES):
        expected[category] = repr([item["value"] for item in inventory["items"]
                                   if item["category"] == category])
    errors = []
    for index, call in enumerate(calls):
        messages = call.get("messages", [])
        prompt = messages[-1].get("content", "") if messages else ""
        stage = index % 6
        markers = [number for number, marker in enumerate(_PROMPT_MARKERS) if marker in prompt]
        if markers != [stage]:
            errors.append("prompt_stage_mismatch")
        source_position = prompt.find(_SOURCE_MARKER)
        next_section = "\nIf " if stage < 3 else "\nEvaluate "
        if source_position < 0 or not prompt[source_position:].startswith(
                _SOURCE_MARKER + passage + next_section):
            errors.append("source_mismatch")
        if not prompt.endswith(expected[_PROMPT_CATEGORIES[stage]]):
            errors.append("candidate_inventory_mismatch")
    return sorted(set(errors))


def audit_native_calls(calls, inventory):
    """Return JSON-safe per-call validity and paired counts for native judge calls.

    Calls are ordered native calls.jsonl records, six per repetition. Unknown,
    excessive, duplicate or malformed incorrect candidates invalidate that
    *whole call*. Such calls have no corrected count or corrected metric.
    """
    candidates = defaultdict(lambda: defaultdict(deque))
    for item in inventory["items"]:
        category = _CATEGORY.get(item["category"])
        if category is None:
            continue
        value = item["value"]
        key = tuple(value[field] for field in _FIELDS[category])
        candidates[category][key].append(item["occurrence_id"])
    rows = []
    calls = list(calls)
    schedule_errors = _verify_schedule(calls, inventory)
    if schedule_errors:
        return {"construction_id": inventory["construction_id"], "call_count": len(calls),
                "schedule_valid": False, "schedule_errors": schedule_errors,
                "repetitions": [], "scope": "structural_format_and_exact_candidate_binding_only"}
    for offset in range(0, len(calls), 6):
        repetition = {"repetition_index": offset // 6 + 1}
        for stage, (category, kind) in enumerate(_STAGES):
            entry = repetition.setdefault(category, {"candidate_count": sum(map(len, candidates[category].values())),
                                                       "reconstructed_native_counts": {}, "corrected_metrics": None})
            call_index = offset + stage
            raw = None
            transport_done = False
            if call_index < len(calls):
                call = calls[call_index]
                response = call.get("response", {})
                raw = response.get("response")
                transport_done = ("transport_error" not in call
                                  and response.get("done") is True
                                  and response.get("done_reason") != "length")
            native = _native_count(raw, category, kind)
            entry["reconstructed_native_counts"][kind] = native
            errors = []
            if not transport_done:
                errors.append("incomplete_transport")
            units = []
            object_count = None
            sentinel = False
            try:
                objects, sentinel = _objects(raw, kind)
                object_count = len(objects)
                for obj in objects:
                    units.extend(_units(obj, category))
            except (_DuplicateKey, ValueError) as exc:
                errors.append(str(exc))
            if not errors and kind == "more" and len(set(units)) != len(units):
                errors.append("duplicate_output")
            matched = []
            if not errors and kind == "incorrect":
                remaining = {key: deque(ids) for key, ids in candidates[category].items()}
                seen = Counter()
                for key in units:
                    if key not in remaining:
                        errors.append("unknown_candidate")
                    elif not remaining[key]:
                        errors.append("overreported_candidate")
                    else:
                        matched.append(remaining[key].popleft())
                    seen[key] += 1
            entry[kind] = {"call_index": call_index + 1 if call_index < len(calls) else None,
                           "valid": not errors, "count": None if errors else len(units),
                           "object_count": object_count, "raw_unit_count": len(units) if object_count is not None else None,
                           "sentinel": sentinel, "matched_occurrence_ids": matched if not errors else [],
                           "errors": sorted(set(errors))}
        for category in ("entity", "event_entity", "relation"):
            entry = repetition[category]
            native = entry["reconstructed_native_counts"]
            native_transport_complete = all("incomplete_transport" not in entry[kind]["errors"]
                                            for kind in ("more", "incorrect"))
            entry["reconstructed_native_metrics"] = (_metric(entry["candidate_count"], native["incorrect"], native["more"])
                                       if native_transport_complete and None not in native.values() else None)
            if entry["more"]["valid"] and entry["incorrect"]["valid"]:
                entry["corrected_metrics"] = _metric(entry["candidate_count"],
                                                     entry["incorrect"]["count"], entry["more"]["count"])
        rows.append(repetition)
    return {"construction_id": inventory["construction_id"], "call_count": len(calls),
            "schedule_valid": True, "schedule_errors": [], "repetitions": rows,
            "scope": "structural_format_and_exact_candidate_binding_only"}
