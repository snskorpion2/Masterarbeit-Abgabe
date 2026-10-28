"""Explicit schema/ID protocol variant; native sources and old runs stay untouched.

One durable request engine owns the ENTIRE retry budget for every active stage.
Native prompt builders are read as AST without running their SDK/retry wrappers.
"""
from __future__ import annotations

import ast
import json
import math
import re
import time
from pathlib import Path

from . import extended_pilot as pilot, extended_measurements as measure
from . import extended_artifacts as artifacts, frozen_questions, mcq_answer_bridge
from .contract import DEFAULT_SOURCE, parse_json, sha256, verify_source, write_json
from .local_runtime import LocalOllama, PROFILES, request_json, CONTEXT, validate_context
from .retry_policy import transient_transport

VARIANT = "local_lamport_reliability_v2_confidence_id_map_retry10_v1"
TRIPLES_ONLY_VARIANT = "local_lamport_reliability_v2_confidence_id_map_retry10_triples_only_v1"
DISABLED_MCQ_STAGES = ("mcq_answers", "mcq_confidence")
CONFIDENCE_PROTOCOL = "fixed_id_keys_v1"
MCQ_PARSER_PROTOCOL = mcq_answer_bridge.PROTOCOL
MAX_TECHNICAL_RETRIES = 10
MAX_TOTAL_ATTEMPTS = 1 + MAX_TECHNICAL_RETRIES
CATEGORIES = ("entity", "event", "relation")
FIELDS = ("entity_relation_dict", "event_entity_relation_dict", "event_relation_dict")
STAGES = ("entity_relation", "event_entity", "event_relation")


def technical_retry_policy():
    return {"policy_id": "technical_retry_10_v1", "max_total_attempts": MAX_TOTAL_ATTEMPTS,
            "max_additional_attempts": MAX_TECHNICAL_RETRIES,
            "additional_attempts_all_active_stages": MAX_TECHNICAL_RETRIES,
            "eligible": ["invalid_format", "invalid_schema_or_ids", "length_abort", "transient_transport"],
            "native_retry_wrappers_used": False, "outcome_based_retries": False,
            "unknown_in_flight": "halt_without_redraw"}


def obj(properties):
    return {"type": "object", "properties": properties, "required": list(properties),
            "additionalProperties": False}


def array(item):
    return {"type": "array", "items": item}


def triple_schema(category, *, missing=False):
    string = {"type": "string", **({"minLength": 1} if missing else {})}
    entities = array(string)
    if missing:
        entities.update(minItems=1, uniqueItems=True)
    return obj({"Event": string, "Entity": entities}) if category == "event" else obj(
        {"Head": string, "Relation": string, "Tail": string})


def schema_for(request):
    kind = request["kind"]
    if kind in {"recall_preprocess", "recall_anchors"}:
        return request["output_schema"]
    if kind == "extraction":
        return array(triple_schema(request["category"]))
    if kind == "more":
        statements = array(triple_schema(request["category"], missing=True))
        statements["uniqueItems"] = True
        return obj({"missing": statements})
    if kind == "incorrect":
        ids = request["item_ids"]
        spec = array({"type": "string", "enum": ids} if ids else {"type": "string"})
        spec.update(uniqueItems=True, maxItems=len(ids))
        return obj({"incorrect_ids": spec})
    if kind == "mcq":
        return {"type": "string", "enum": list("ABCDE" if request["variant"] == "ae" else "ABCD")}
    if kind == "confidence":
        protocol = request.get("confidence_protocol")
        if protocol is not None:
            if protocol != CONFIDENCE_PROTOCOL:
                raise ValueError("Unknown confidence protocol")
            ids = request["item_ids"]
            if (not ids or not all(isinstance(ident, str) and ident for ident in ids)
                    or len(ids) != len(set(ids))):
                raise ValueError("Confidence batch IDs must be nonempty unique strings")
            return obj({ident: {"type": "number", "minimum": 0, "maximum": 10} for ident in ids})
        # Historical saved requests retain their original array contract.
        items = array(obj({"id": {"type": "string", "enum": request["item_ids"]},
                          "confidence_score": {"type": "number", "minimum": 0, "maximum": 10}}))
        items.update(minItems=len(request["item_ids"]), maxItems=len(request["item_ids"]))
        return obj({"judgments": items})
    raise ValueError("Unknown reliability request kind")


def validate(value, schema):
    """Exhaustive local check of every keyword we generate, even if decoder ignores it."""
    supported = {"type", "properties", "required", "additionalProperties", "items", "enum",
                 "minimum", "maximum", "minItems", "maxItems", "uniqueItems", "minLength"}
    if set(schema) - supported:
        raise ValueError("Unsupported local validation keyword")
    typ = schema["type"]
    valid = {"object": isinstance(value, dict), "array": isinstance(value, list),
             "string": isinstance(value, str),
             "number": type(value) in (int, float) and math.isfinite(value)}
    if not valid.get(typ, False):
        raise ValueError("Schema type mismatch")
    if "enum" in schema and value not in schema["enum"]:
        raise ValueError("Unknown ID or value")
    if typ == "string" and len(value) < schema.get("minLength", 0):
        raise ValueError("Empty statement field")
    if typ == "object":
        if set(value) != set(schema["required"]):
            raise ValueError("Missing or additional object fields")
        for key, child in value.items():
            _validate_child(child, schema["properties"][key], key)
    if typ == "array":
        if not schema.get("minItems", 0) <= len(value) <= schema.get("maxItems", float("inf")):
            raise ValueError("Array cardinality mismatch")
        if schema.get("uniqueItems") and len({artifacts.digest(x) for x in value}) != len(value):
            raise ValueError("Duplicate IDs")
        for index, child in enumerate(value):
            _validate_child(child, schema["items"], index)
    if typ == "number" and not schema.get("minimum", -math.inf) <= value <= schema.get("maximum", math.inf):
        raise ValueError("Number outside permitted range")


def _validate_child(value, schema, coordinate):
    try:
        validate(value, schema)
    except ValueError as exc:
        # Add structured location without changing legacy type/message/acceptance.
        exc.absolute_path = [coordinate, *getattr(exc, "absolute_path", [])]
        raise


def classify(request, raw):
    bridges = []
    if request["kind"] == "mcq" and request.get("mcq_parser_protocol") is not None:
        if request["mcq_parser_protocol"] != MCQ_PARSER_PROTOCOL:
            raise ValueError("Unknown MCQ parser protocol")
        # A complete JSON string and a raw answer are the only wire forms.
        # Do not turn malformed JSON or object wrappers into selections.
        if not isinstance(raw, str):
            raise ValueError("MCQ response must be text")
        json_string = raw.lstrip().startswith('"')
        value = parse_json(raw) if json_string else raw
        if json_string and not isinstance(value, str):
            raise ValueError("MCQ JSON value must be a string")
        answer, reason = mcq_answer_bridge.select_answer(value, request["visible_options"], request["variant"])
        validate(answer, schema_for(request))
        if json_string:
            bridges.append("json_string_to_letter")
        if reason == "full_matching_option_text":
            bridges.append(reason)
        elif not json_string:
            bridges.append("raw_letter_to_letter")
        return {"answer": answer, "abstained": answer == "E", "format_bridge": "+".join(bridges),
                "format_bridges": bridges}
    if request["kind"] == "confidence" and request.get("confidence_protocol") is not None:
        # Check the wire format BEFORE canonicalization. No wrapper/array fallback.
        value = parse_json(raw)
        validate(value, schema_for(request))
        value, bridge = measure.confidence_container(value, request["item_ids"])
        return {"judgments": measure.validate_confidence(value, request["item_ids"]),
                "format_bridge": bridge, "format_bridges": [bridge] if bridge else []}
    if request["kind"] == "confidence":
        # Only already-approved, complete lossless containers are accepted.
        value = measure.parse_json_response(raw)
        fence = measure.FENCE.fullmatch(raw)
        if fence:
            bridges.append("complete_json_fence")
        if isinstance(parse_json(fence["body"] if fence else raw), list):
            bridges.append("json_array_to_judgments")
        value, bridge = measure.confidence_container(value, request["item_ids"], allow_id_reorder=True)
        if bridge:
            bridges.append(bridge)
    else:
        value = parse_json(raw)
    validate(value, schema_for(request))
    if request["kind"] in {"recall_preprocess", "recall_anchors"}:
        from .recall_methods import validate_response
        return validate_response(request, value)
    if request["kind"] == "confidence":
        return {"judgments": measure.validate_confidence(value, request["item_ids"]),
                "format_bridge": "+".join(bridges) if bridges else None, "format_bridges": bridges}
    if request["kind"] == "mcq":
        return {"answer": value, "abstained": value == "E", "format_bridge": "json_string_to_letter",
                "format_bridges": ["json_string_to_letter"]}
    if request["kind"] == "more":
        # Structural units only: no semantic equivalence or source-support test.
        units = []
        for statement in value["missing"]:
            if request["category"] == "event":
                fields = [statement["Event"], *statement["Entity"]]
                units.extend((statement["Event"], entity) for entity in statement["Entity"])
            else:
                fields = [statement[key] for key in ("Head", "Relation", "Tail")]
                units.append(tuple(fields))
            if any(not field.strip() for field in fields):
                raise ValueError("Empty missing-statement field")
        if len(units) != len(set(units)):
            raise ValueError("Duplicate missing-statement unit")
        if request.get("missing_consistency_protocol") is not None:
            from .technical_repairs import MISSING_PROTOCOL
            if request["missing_consistency_protocol"] != MISSING_PROTOCOL:
                raise ValueError("Unknown missing-statement consistency protocol")
            existing = {tuple(unit) for unit in request["existing_native_units"]}
            overlap = next((unit for unit in units if unit in existing), None)
            if overlap is not None:
                raise ValueError("Missing-statement unit already present in native extraction: " + repr(overlap))
    return value


def metrics(n, incorrect, missing, category):
    result = {key: None for key in ("precision", "recall", "f1")}
    result.update({key + "_reason": None for key in result.copy()})
    result.update(candidate_count=n, incorrect_count=None, correct_count=None, missing_count=None,
                  metric_definition="unrounded_counts_v2")
    if incorrect["status"] != "valid":
        for key in ("precision", "recall", "f1"):
            result[key + "_reason"] = "invalid_incorrect_judgment"
        return result
    wrong = len(incorrect["parsed"]["incorrect_ids"])
    if wrong > n:
        raise ValueError("Incorrect count exceeds candidates")
    correct = n - wrong
    result.update(incorrect_count=wrong, correct_count=correct)
    result["precision"] = correct / n if n else None
    result["precision_reason"] = None if n else "zero_denominator"
    if missing["status"] != "valid":
        result.update(recall_reason="invalid_missing_judgment", f1_reason="invalid_missing_judgment")
        return result
    values = missing["parsed"]["missing"]
    more = sum(len(x["Entity"]) for x in values) if category == "event" else len(values)
    result["missing_count"] = more
    result["recall"] = correct / (correct + more) if correct + more else None
    result["recall_reason"] = None if correct + more else "zero_denominator"
    # Conventional F1 count formula, with explicit zero denominator.
    if n and correct + more:
        denominator = 2 * correct + wrong + more
        result["f1"] = 2 * correct / denominator if denominator else None
        result["f1_reason"] = None if denominator else "zero_denominator"
    else:
        result["f1_reason"] = "zero_denominator"
    return result


def immutable(path, value):
    from . import immutable_publish
    if immutable_publish.enabled():
        return immutable_publish.publish_json(path, value)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if not immutable_publish.equal_json(immutable_publish.read_json(path), value):
            raise ValueError(f"Immutable reliability artifact changed: {path.name}")
    else:
        with path.open("x", encoding="utf-8") as stream:
            json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)


def _request_messages(request):
    return request["messages"] if "messages" in request else [{"role": "user", "content": request["prompt"]}]


def _from_transport(request, transport, model, *, classifier_fn=None):
    record = {"request_id": request["request_id"], "kind": request["kind"],
              "item_ids": request.get("item_ids", []), "model": model,
              "request_sha256": artifacts.digest(request),
              "transport_call_sha256": pilot._transport_hash(transport),
              "inference_dispatched": transport.get("inference_dispatched") is True}
    response = transport.get("response", {})
    raw = response.get("response")
    record.update(raw_response=raw, done_reason=response.get("done_reason"),
                  usage={key: response.get(key) for key in ("prompt_eval_count", "eval_count", "total_duration")})
    if not pilot._transport_valid(transport, model):
        record.update(status="transport_error",
                      retry_allowed=transport.get("transport_error", {}).get("retryable_transient") is True)
    elif response.get("done_reason") == "length":
        record.update(status="length_abort", retry_allowed=True)
    else:
        try:
            effective = raw
            if request["kind"] in ("more", "incorrect") and request.get("judge_set_protocol") is not None:
                from . import judge_set_bridge
                effective, bridge_audit = judge_set_bridge.prepare(request, raw)
                if bridge_audit is not None:
                    record["judge_set_bridge"] = bridge_audit
            if request.get("exact_missing_protocol") is not None:
                from . import exact_missing_repair
                effective, repair_audit = exact_missing_repair.prepare(request, effective)
                record["exact_missing_repair"] = repair_audit
                record["effective_response"] = effective
            record.update(status="valid", parsed=(classifier_fn or classify)(request, effective), retry_allowed=False)
        except (ValueError, TypeError, KeyError) as exc:
            record.update(status="invalid_format", retry_allowed=True)
            if request.get("missing_consistency_protocol") is not None:
                record["validation_error"] = str(exc)
            if request.get("diagnostic_protocol") == "validation_detail_v1":
                record["validation_diagnostic"] = _exception_diagnostic(exc)
    if request.get("adaptive_output_protocol") is not None:
        record["effective_max_new_tokens"] = transport.get("options", {}).get("num_predict")
    if request.get("adaptive_output_protocol") == "adaptive_output_budget_v2" and record["status"] in (
            "valid", "invalid_format", "length_abort"):
        from .technical_repairs import OUTPUT_SAFETY_TOKENS
        options = transport.get("options", {})
        cap, context = options.get("num_predict"), options.get("num_ctx")
        prompt, output = response.get("prompt_eval_count"), response.get("eval_count")
        measured = transport.get("hf_prompt_tokens")
        if (transport.get("adaptive_output_v2") is True
                and type(cap) is int and cap > 0 and type(context) is int and context > 0
                and type(prompt) is int and prompt >= 0 and prompt == measured
                and type(output) is int and 0 <= output <= cap
                and prompt + cap + OUTPUT_SAFETY_TOKENS <= context):
            if record["status"] == "length_abort":
                if output == cap:
                    record["verified_length_abort"] = True
                else:
                    record.update(status="transport_error", retry_allowed=False,
                                  validation_error="Unverified length or incoherent token counts")
        else:
            record.update(status="transport_error", retry_allowed=False,
                          validation_error="Unverified output transport or incoherent token counts")
    return record


def _exception_diagnostic(exc):
    cause = exc
    while cause.__cause__ is not None:
        cause = cause.__cause__
    result = {"error_class": type(exc).__name__, "message": str(exc),
              "field_path": list(getattr(cause, "absolute_path", []))}
    if cause is not exc:
        result["cause"] = {"error_class": type(cause).__name__, "message": str(cause)}
    return result


def _final_from_attempts(attempts):
    final = dict(attempts[-1])
    exhausted = (final["status"] != "valid" and final.get("retry_allowed") is True
                 and len(attempts) == MAX_TOTAL_ATTEMPTS)
    final.update(attempts=attempts, first_status=attempts[0]["status"],
                 final_status=final["status"], technical_retry_count=len(attempts) - 1,
                 attempt_count=len(attempts),
                 physical_inference_dispatches=sum(x.get("inference_dispatched") is True for x in attempts),
                 retry_budget_exhausted=exhausted, retry_policy=technical_retry_policy(),
                 termination_reason=("valid" if final["status"] == "valid" else "budget_exhausted" if exhausted
                                     else "missing_dependency" if final["status"] == "missing_dependency"
                                     else "non_retryable_error"))
    return final


def audit_existing(path, schedule, model, *, classifier_fn=None, context=CONTEXT):
    """Reconcile every cached attempt with its intent and raw transport record."""
    from . import immutable_publish
    validate_context(context, model)
    path = Path(path)
    intents = pilot._records(path / "dispatch_intents.jsonl")
    completions = pilot._records(path / "attempts.jsonl")
    calls = pilot._records(path / "calls.jsonl")
    by_request = {x["request_id"]: x for x in schedule}
    if len(by_request) != len(schedule):
        raise ValueError("Duplicate logical request ID")
    by_intent, recorded, raw_by_id = {}, {}, {}
    for intent in intents:
        request = by_request.get(intent.get("request_id"))
        aid = intent.get("attempt_id")
        number = intent.get("attempt_number")
        if (request is None or type(number) is not int or not 1 <= number <= MAX_TOTAL_ATTEMPTS
                or aid != request["request_id"] + f":attempt:{number}"
                or intent.get("request_sha256") != artifacts.digest(request) or aid in by_intent):
            raise ValueError("Cached attempt intent differs from request schedule")
        if (request.get("adaptive_output_protocol") == "adaptive_output_budget_v2"
                and intent.get("adaptive_output_v2") is not True):
            raise ValueError("Adaptive output intent lacks the safety dispatch setting")
        by_intent[aid] = intent
    for call in calls:
        aid = call.get("request_identity")
        if aid not in by_intent or aid in raw_by_id:
            raise ValueError("Missing, duplicate or unmatched raw transport identity")
        request = by_request[by_intent[aid]["request_id"]]
        if not immutable_publish.equal_json(call.get("messages"), _request_messages(request)):
            raise ValueError("Raw transport messages differ from the request")
        if context != CONTEXT and call.get("options", {}).get("num_ctx") != context:
            raise ValueError("Raw transport context differs from frozen context")
        if request.get("adaptive_output_protocol") == "adaptive_output_budget_v2":
            from .technical_repairs import OUTPUT_SAFETY_TOKENS
            count, cap = call.get("hf_prompt_tokens"), call.get("options", {}).get("num_predict")
            if (call.get("adaptive_output_v2") is not True
                    or by_intent[aid].get("adaptive_output_v2") is not True
                    or call.get("options", {}).get("num_ctx") != context or type(count) is not int or count < 0
                    or type(cap) is not int or cap <= 0 or count + cap + OUTPUT_SAFETY_TOKENS > context):
                raise ValueError("Raw adaptive output admission differs from verified context")
        raw_by_id[aid] = call
    if context != CONTEXT:
        metadata_path = path / "local_runtime.json"
        if intents and not metadata_path.is_file():
            raise ValueError("Dispatched stage lacks runtime context metadata")
        if metadata_path.is_file():
            metadata = parse_json(metadata_path.read_text(encoding="utf-8"))
            if metadata.get("context_tokens") != context:
                raise ValueError("Runtime context metadata differs from frozen context")
        for intent in intents:
            if intent.get("context_tokens") != context:
                raise ValueError("Dispatch intent context differs from frozen context")
    for record in completions:
        aid = record.get("attempt_id")
        if aid in recorded:
            raise ValueError("Duplicate attempt checkpoint")
        intent = by_intent.get(aid)
        request = by_request.get(record.get("request_id"))
        number = record.get("attempt_number")
        if (request is None or type(number) is not int or not 1 <= number <= MAX_TOTAL_ATTEMPTS
                or aid != request["request_id"] + f":attempt:{number}"
                or record.get("kind") != request["kind"]
                or record.get("item_ids") != request.get("item_ids", [])):
            raise ValueError("Cached attempt identity differs from request schedule")
        raw = raw_by_id.get(aid)
        if raw is not None:
            if intent is None:
                raise ValueError("Raw attempt lacks dispatch intent")
            expected = _from_transport(request, raw, model, classifier_fn=classifier_fn)
            if request.get("exact_missing_protocol") is not None:
                for key in ("exact_missing_repair", "effective_response"):
                    if (key in record) != (key in expected):
                        raise ValueError("Cached attempt differs from raw transport: " + key)
            if (immutable_publish.enabled() and request.get("judge_set_protocol") is not None
                    and ("judge_set_bridge" in record) != ("judge_set_bridge" in expected)):
                raise ValueError("Cached attempt differs from raw transport: bridge presence")
            # A runtime postcondition can invalidate an otherwise valid transport.
            postcondition = (expected["status"] in ({"valid", "length_abort"} if request.get("adaptive_output_protocol") ==
                             "adaptive_output_budget_v2" else {"valid"}) and record.get("status") == "transport_error"
                             and record.get("retry_allowed") is False)
            for key, value in expected.items():
                if key in {"status", "retry_allowed"} and postcondition:
                    continue
                if not immutable_publish.equal_json(record.get(key), value):
                    raise ValueError("Cached attempt differs from raw transport: " + key)
        elif intent is None:
            if (request.get("skip_reason") is None or record.get("status") != "missing_dependency"
                    or record.get("reason") != request["skip_reason"] or record.get("dispatched") is not False):
                raise ValueError("Cached nontransport attempt lacks a valid skip reason")
        elif (record.get("status") != "transport_error" or record.get("dispatched") is not False
              or record.get("inference_dispatched") is True or record.get("transport_call_sha256") is not None
              or "parsed" in record or type(record.get("retry_allowed")) is not bool):
            raise ValueError("Cached attempt has no matching raw transport")
        recorded[aid] = record
    for intent in intents:
        request = by_request[intent["request_id"]]
        if request.get("adaptive_output_protocol") is None:
            continue
        from .technical_repairs import effective_output_budget
        number = intent["attempt_number"]
        prior_id = request["request_id"] + f":attempt:{number - 1}"
        if number > 1 and prior_id not in recorded:
            raise ValueError("Adaptive output budget lacks previous frozen attempt")
        if number > 1 and recorded[prior_id].get("retry_allowed") is not True:
            raise ValueError("Adaptive attempt follows a terminal result")
        expected = effective_output_budget(request, recorded.get(prior_id), context)
        if intent.get("effective_max_new_tokens") != expected:
            raise ValueError("Frozen adaptive output budget differs from attempt history")
        raw = raw_by_id.get(intent["attempt_id"])
        if raw is not None and raw.get("options", {}).get("num_predict") != expected:
            raise ValueError("Raw transport output budget differs from frozen intent")
        record = recorded.get(intent["attempt_id"])
        if record is not None and record.get("effective_max_new_tokens") != expected:
            raise ValueError("Attempt output budget differs from frozen intent")
    finals_path = path / "final_responses.json"
    if finals_path.is_file():
        finals = parse_json(finals_path.read_text(encoding="utf-8"))
        if (not isinstance(finals, list) or len(finals) != len(schedule)
                or any(not isinstance(final, dict) or type(final.get("attempt_count")) is not int
                       or not 1 <= final["attempt_count"] <= MAX_TOTAL_ATTEMPTS
                       or final.get("request_id") != request["request_id"]
                       or any(request["request_id"] + f":attempt:{number}" not in recorded
                              for number in range(1, final["attempt_count"] + 1))
                       or not immutable_publish.equal_json(final, _final_from_attempts([
                           recorded[request["request_id"] + f":attempt:{number}"]
                           for number in range(1, final["attempt_count"] + 1)]))
                       for request, final in zip(schedule, finals))):
            raise ValueError("Cached final response differs from attempts")
    return intents, recorded, raw_by_id


def requests(path, schedule, model, *, variant=VARIANT, schema_fn=None, classifier_fn=None,
             protocol_id=None, context=CONTEXT):
    """At most eleven attempts/dispatches, owned by this single stage-independent engine.

    Unknown in-flight outcome halts, never automatically redraws or counts as valid.
    Raw completed calls are reconciled by explicit request/attempt identity.
    """
    validate_context(context, model)
    path = Path(path)
    if any(value is not None for value in (schema_fn, classifier_fn, protocol_id)) and not all(
            value is not None for value in (schema_fn, classifier_fn, protocol_id)):
        raise ValueError("Custom request protocol requires schema, classifier and protocol ID together")
    if protocol_id is not None and (not isinstance(protocol_id, str) or not protocol_id):
        raise ValueError("Custom protocol ID must be a nonempty string")
    path.mkdir(parents=True, exist_ok=True)
    schedule_record = {"model": model, "variant": variant,
                       "retry_policy": technical_retry_policy(), "requests": schedule}
    if protocol_id is not None:
        schedule_record["protocol_id"] = protocol_id
    if context != CONTEXT:
        schedule_record["context_tokens"] = context
    immutable(path / "schedule.json", schedule_record)
    intents, recorded, raw_by_id = audit_existing(path, schedule, model, classifier_fn=classifier_fn,
                                                 context=context)
    by_id = {x["request_id"]: x for x in schedule}
    for intent in intents:
        aid = intent["attempt_id"]
        request = by_id[intent["request_id"]]
        if intent["request_sha256"] != artifacts.digest(request):
            raise ValueError("Attempt request changed")
        if aid in recorded:
            continue
        if aid not in raw_by_id:
            raise RuntimeError(f"Unknown in-flight outcome, refusing automatic redraw: {aid}")
        record = _from_transport(request, raw_by_id[aid], model, classifier_fn=classifier_fn)
        record.update(attempt_id=aid, attempt_number=intent["attempt_number"], recovered=True)
        pilot._append(path / "attempts.jsonl", record)
        recorded[aid] = record
    runtime = None
    finals = []
    try:
        for request in schedule:
            attempts = []
            for number in range(1, MAX_TOTAL_ATTEMPTS + 1):
                aid = request["request_id"] + f":attempt:{number}"
                adaptive = request.get("adaptive_output_protocol") is not None
                if adaptive:
                    from .technical_repairs import effective_output_budget
                    budget = effective_output_budget(request, attempts[-1] if attempts else None, context)
                    parameters = {**request["parameters"], "max_new_tokens": budget}
                else:
                    parameters = request.get("parameters", {})
                if aid in recorded:
                    record = recorded[aid]
                elif request.get("skip_reason"):
                    record = {"request_id": request["request_id"], "kind": request["kind"],
                              "item_ids": request.get("item_ids", []), "status": "missing_dependency",
                              "reason": request["skip_reason"], "retry_allowed": False,
                              "attempt_id": aid, "attempt_number": number, "dispatched": False}
                    pilot._append(path / "attempts.jsonl", record)
                    recorded[aid] = record
                else:
                    if runtime is None:
                        runtime = (LocalOllama(model, path) if context == CONTEXT
                                   else LocalOllama(model, path, context=context))
                    intent = {"attempt_id": aid, "request_id": request["request_id"],
                              "attempt_number": number, "request_sha256": artifacts.digest(request)}
                    if adaptive:
                        intent["effective_max_new_tokens"] = budget
                    if request.get("adaptive_output_protocol") == "adaptive_output_budget_v2":
                        intent["adaptive_output_v2"] = True
                    if context != CONTEXT:
                        intent["context_tokens"] = context
                    pilot._append(path / "dispatch_intents.jsonl", intent)
                    try:
                        kwargs = {"json_schema": (schema_fn or schema_for)(request), "request_identity": aid}
                        if request.get("adaptive_output_protocol") == "adaptive_output_budget_v2":
                            kwargs["adaptive_output_v2"] = True
                        runtime.generate(_request_messages(request), parameters, **kwargs)
                    except Exception as exc:
                        # Setup/context errors can occur before a transport record.
                        calls = pilot._records(path / "calls.jsonl")
                        call = next((x for x in reversed(calls) if x.get("request_identity") == aid), None)
                        if call is None:
                            record = {"request_id": request["request_id"], "kind": request["kind"],
                                      "item_ids": request.get("item_ids", []), "status": "transport_error",
                                      "error_type": type(exc).__name__, "error_message": str(exc),
                                      "retry_allowed": transient_transport(exc), "dispatched": False}
                            if adaptive:
                                record["effective_max_new_tokens"] = budget
                        else:
                            record = _from_transport(request, call, model, classifier_fn=classifier_fn)
                            # Runtime postconditions (e.g. thinking/count drift) stay invalid.
                            if record["status"] == "valid" or (
                                    request.get("adaptive_output_protocol") == "adaptive_output_budget_v2"
                                    and record["status"] == "length_abort"):
                                record.update(status="transport_error", retry_allowed=False)
                        if request.get("diagnostic_protocol") == "validation_detail_v1":
                            record["runtime_diagnostic"] = _exception_diagnostic(exc)
                    else:
                        record = _from_transport(request, pilot._last_transport_record(path / "calls.jsonl"), model,
                                                 classifier_fn=classifier_fn)
                    record.update(attempt_id=aid, attempt_number=number)
                    pilot._append(path / "attempts.jsonl", record)
                    recorded[aid] = record
                attempts.append(record)
                if not record.get("retry_allowed"):
                    break
            finals.append(_final_from_attempts(attempts))
    finally:
        if runtime is not None:
            runtime.close()
            if model == pilot.JUDGE and getattr(runtime, "inference_dispatched", False) is True:
                request_json("/api/generate", {"model": runtime.name, "keep_alive": 0})
    immutable(path / "final_responses.json", finals)
    return finals


def native_extraction_prompts(source):
    tree = ast.parse((DEFAULT_SOURCE / "atlas_rag/llm_generator/prompt/triple_extraction_prompt.py").read_text(encoding="utf-8"))
    instructions = ast.literal_eval(tree.body[0].value)["en"]
    return [[{"role": "system", "content": instructions["system"]},
             {"role": "user", "content": instructions[stage] + "\n" + source}] for stage in STAGES]


def native_judge_prompts(source, row):
    """Execute only the two pure original prompt builders, injecting a capture sink."""
    path = DEFAULT_SOURCE / "EvaluateKGC/TripleAccuracy/triple_acc.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    functions = [node for node in tree.body if isinstance(node, ast.FunctionDef)
                 and node.name in {"get_more", "get_incorrect"}]
    captured = []
    namespace = {"response": lambda prompt: captured.append(prompt)}
    exec(compile(ast.Module(body=functions, type_ignores=[]), str(path), "exec"), namespace)
    values = [row[field] for field in FIELDS]
    namespace["get_more"](source, *values)
    namespace["get_incorrect"](source, *values)
    return captured


def judge_requests(inventory, row):
    originals = native_judge_prompts(row["original_text"], row)
    result = []
    for repeat in range(1, 4):
        for stage, original in enumerate(originals):
            category = CATEGORIES[stage % 3]
            kind = "more" if stage < 3 else "incorrect"
            candidates = [x for x in inventory["items"] if x["category"] ==
                          ("event_entity_link" if category == "event" else category)]
            ids = [x["occurrence_id"] for x in candidates]
            # All original content criteria remain verbatim. Explicitly override
            # only serialization instructions, not support/interpretation criteria.
            protocol = ("Return exactly a JSON object with incorrect_ids, an array of the IDs of incorrect candidates. "
                        "An empty array means all correct. Never copy triples or invent IDs. "
                        "For EV, each ID denotes one listed Event/Entity participation.\nCandidate identity mapping:\n"
                        + json.dumps([{"id": x["occurrence_id"], "value": x["value"]} for x in candidates], ensure_ascii=False)
                        if kind == "incorrect" else
                        "Return exactly a JSON object with missing, an array of missing statements in the original triple object format. "
                        "An empty array means all recognized. Missing statements are NOT restricted to existing candidate IDs.")
            prompt = original + ("\n\nOUTPUT PROTOCOL OVERRIDE (separate reliability_v2 method variant): "
                     "Keep every substantive judgment criterion above unchanged. Only replace the requested line-wise/text output protocol. "
                     + protocol)
            ident = inventory.get("construction_id", "c1")
            result.append({"request_id": f"{ident}:judge:r{repeat}:{category}:{kind}", "kind": kind,
                           "category": category, "repeat": repeat, "item_ids": ids,
                           "prompt": prompt, "original_prompt": original,
                           "messages": [{"role": "system", "content": "You are a helpful assistant."},
                                        {"role": "user", "content": prompt}], "parameters": {}})
    return result


def preflight(output, questions_path, *, include_mcqs=True):
    pre = pilot.preflight(output, questions_path)
    pre.update(variant=VARIANT, judge_protocol="candidate_ids_precision_free_missing",
               confidence_protocol=CONFIDENCE_PROTOCOL,
               mcq_parser_protocol=MCQ_PARSER_PROTOCOL,
               retry_policy=technical_retry_policy(),
               decoding={"nemotron": "completion.json_schema", "qwen": "generate.format",
                         "mcq_decoder_schema": "JSON string containing exactly one allowed letter",
                         "mcq_format_bridge": MCQ_PARSER_PROTOCOL,
                         "local_exhaustive_validation": True},
               extraction_output_tokens=2048)
    if not include_mcqs:
        pre.update(variant=TRIPLES_ONLY_VARIANT, evaluation_scope="triples_only",
                   disabled_stages=list(DISABLED_MCQ_STAGES))
    return pre


def confidence_request(ident, items):
    prompt = measure.confidence_batch_prompt(items)
    original = ("Return exactly one JSON object with judgments in input order, each containing only "
                "id and confidence_score.")
    replacement = ("Return exactly one JSON object whose property names are exactly the prior item IDs "
                   "and whose property values are their numeric confidence scores. Include every ID "
                   "exactly once, with no additional properties, nested objects, arrays or wrappers. "
                   "Decimal scores are allowed within the same 0-10 scale.")
    if prompt.count(original) != 1:
        raise ValueError("Confidence prompt output instruction changed")
    prompt = prompt.replace(original, replacement, 1)
    return {"request_id": ident, "kind": "confidence", "item_ids": [x["id"] for x in items],
            "confidence_protocol": CONFIDENCE_PROTOCOL, "prompt": prompt,
            "parameters": {"max_new_tokens": 128 + 256 * len(items)}}


def stage_attempt_counts(rows):
    return {"logical_requests": len(rows), "valid": sum(x["status"] == "valid" for x in rows),
            "attempt_count": sum(x["attempt_count"] for x in rows),
            "physical_inference_dispatches": sum(x["physical_inference_dispatches"] for x in rows),
            "technical_retries": sum(x["technical_retry_count"] for x in rows),
            "retry_budget_exhausted": sum(x["retry_budget_exhausted"] for x in rows)}


def assess_extraction(folder, inventory, row, ne_items, *, variant=VARIANT, include_mcqs=True):
    """Shared passive measurement path for a frozen extraction and its actual producers."""
    folder = Path(folder)
    ident = inventory["construction_id"]
    # Omit the optional argument on the historical path to preserve existing callers.
    def collect(name, schedule, model):
        if variant == VARIANT:
            return requests(folder / name, schedule, model)
        return requests(folder / name, schedule, model, variant=variant)

    judge_schedule = judge_requests(inventory, row)
    judged = collect("triple_judgments", judge_schedule, pilot.JUDGE)
    mcq_schedule = pilot._mcq_requests(inventory, mcq_parser_protocol=MCQ_PARSER_PROTOCOL) if include_mcqs else []
    mcqs = collect("mcq_answers", mcq_schedule, pilot.JUDGE) if include_mcqs else []
    ne_batches = []
    for item in ne_items:
        if (not ne_batches or len(ne_batches[-1]) == pilot.CONFIDENCE_BATCH
                or ne_batches[-1][0]["producer_index"] != item["producer_index"]):
            ne_batches.append([])
        ne_batches[-1].append(item)
    conf_ne = [confidence_request(f"{ident}:nemotron-confidence:{index:05d}", batch)
               for index, batch in enumerate(ne_batches)]
    conf_qw, mcq_conf_items = [], []
    for schedule, results, event in ((judge_schedule, judged, "id_triple_judgment"),
                                    (mcq_schedule, mcqs, "mcq_answer")):
        for req, result in zip(schedule, results):
            request_id = req["request_id"]
            target = "mcq_abstention" if event == "mcq_answer" and result.get("parsed", {}).get("answer") == "E" else event
            item = {"id": request_id, "event": target, "original_input": _request_messages(req),
                    "original_response": result.get("raw_response")}
            if event == "mcq_answer" and result["status"] == "valid":
                mcq_conf_items.append(item)
            else:
                confidence = confidence_request(request_id + ":confidence", [item])
                if result["status"] != "valid":
                    confidence["skip_reason"] = "invalid_prior_result"
                conf_qw.append(confidence)
    for start in range(0, len(mcq_conf_items), pilot.MCQ_CONFIDENCE_BATCH):
        conf_qw.append(confidence_request(f"{ident}:mcq-confidence:{start//pilot.MCQ_CONFIDENCE_BATCH:05d}",
                                         mcq_conf_items[start:start + pilot.MCQ_CONFIDENCE_BATCH]))
    ne = collect("confidence_nemotron", conf_ne, pilot.CONSTRUCTOR)
    qw = collect("confidence_qwen", conf_qw, pilot.JUDGE)
    metric_rows = []
    for repeat in range(3):
        for index, category in enumerate(CATEGORIES):
            inc, missing = judged[repeat * 6 + index + 3], judged[repeat * 6 + index]
            n = len(judge_schedule[repeat * 6 + index]["item_ids"])
            metric_rows.append({"repeat": repeat + 1, "category": category,
                                **metrics(n, inc, missing, category)})
    validity = {"variant": variant, "metrics": metric_rows}
    if not include_mcqs:
        validity.update(evaluation_scope="triples_only", disabled_stages=list(DISABLED_MCQ_STAGES))
    immutable(folder / "metric_validity.json", validity)
    return {"triple_judgments": judged, "mcq_answers": mcqs, "confidence_nemotron": ne, "confidence_qwen": qw}


def execute(output, pre):
    include_mcqs = pre.get("evaluation_scope") != "triples_only"
    expected_variant = VARIANT if include_mcqs else TRIPLES_ONLY_VARIANT
    if pre.get("variant") != expected_variant:
        raise ValueError("Preflight evaluation scope and variant disagree")
    output = Path(output).resolve()
    summary_path = output / "technical_summary.json"
    if output.exists():
        if not summary_path.exists() or json.loads(summary_path.read_text(encoding="utf-8")).get("preflight") != pre:
            raise ValueError("Cannot reuse a different or uncheckpointed output directory")
    output.mkdir(parents=True, exist_ok=True)
    prior = json.loads(summary_path.read_text(encoding="utf-8")) if summary_path.exists() else {}
    summary = {"preflight": pre, "status": "running", "analysis_performed": False,
               "retry_policy": technical_retry_policy(),
               "started_utc": prior.get("started_utc", pilot._now()),
               "resume_count": prior.get("resume_count", -1) + 1,
               "active_seconds": prior.get("active_seconds", 0)}
    if not include_mcqs:
        summary.update(evaluation_scope="triples_only", disabled_stages=list(DISABLED_MCQ_STAGES))
    started = time.perf_counter()
    write_json(summary_path, summary)
    try:
        source = re.sub(r"\s+", " ", pilot.ARTICLE.read_text(encoding="utf-8-sig")).strip()
        input_manifest = {"article_path": str(pilot.ARTICLE),
                  "article_sha256": pre["article_sha256"], "article_count": 1,
                  "native_normalized_source": source, "source_sha256": artifacts.digest(source),
                  "preprocessing": "UTF-8-sig decode, native remove_doc_spaces whitespace collapse"}
        if not include_mcqs:
            input_manifest.update(evaluation_scope="triples_only", disabled_stages=list(DISABLED_MCQ_STAGES))
        immutable(output / "input_manifest.json", input_manifest)
        extraction_schedule = []
        for category, messages in zip(CATEGORIES, native_extraction_prompts(source)):
            extraction_schedule.append({"request_id": "c1:extraction:" + category, "kind": "extraction",
                "category": category, "item_ids": [], "messages": messages, "prompt": messages[-1]["content"],
                "parameters": {"max_new_tokens": 2048, "temperature": 0.7, "do_sample": True,
                               "repetition_penalty": 1.0, "return_full_text": False, "truncation": True, "padding": False}})
        folder = output / "c1"
        extraction = (requests(folder / "construct", extraction_schedule, pilot.CONSTRUCTOR)
                      if include_mcqs else requests(folder / "construct", extraction_schedule,
                                                    pilot.CONSTRUCTOR, variant=expected_variant))
        if any(x["status"] != "valid" for x in extraction):
            counts = stage_attempt_counts(extraction)
            summary["technical_counts"] = {**counts, "by_stage": {"construct": counts}}
            summary.update(status="technical_gaps_uninterpreted", failed_dependency="extraction")
            return 2
        row = {"id": "lamport", "original_text": source, **{field: x["parsed"] for field, x in zip(FIELDS, extraction)}}
        extraction_path = folder / "extraction.jsonl"
        if not extraction_path.exists():
            pilot._append(extraction_path, row)
        elif pilot._records(extraction_path) != [row]:
            raise ValueError("Immutable extraction changed")
        revised, provenance = frozen_questions.prepare(Path(pre["questions_path"]), pilot.ARTICLE)
        if provenance != pre["question_version"] or artifacts.digest(revised) != pre["revised_questions_sha256"]:
            raise ValueError("Question provenance changed after preflight")
        question_path = frozen_questions.persist(output / "frozen_questions", revised, provenance)
        questions = artifacts.load_questions(question_path)
        inventory = {"construction_id": "c1", "items": artifacts.inventory_extraction(extraction_path, "c1"),
                     "concepts": [], "induction_enabled": False,
                     "extraction_file": str(extraction_path), "extraction_sha256": sha256(extraction_path),
                     "questions_file": str(question_path), "questions_sha256": sha256(question_path),
                     "native_context_record": artifacts.native_context_record(extraction_path, questions)}
        immutable(folder / "inventory.json", inventory)
        # Confidence remains a separate passive call about the exact stored result.
        ne_items = []
        for index, item in enumerate(inventory["items"]):
            category = "event" if item["category"] == "event_entity_link" else item["category"]
            producer_index = CATEGORIES.index(category)
            ident = item["occurrence_id"]
            ne_items.append({"id": ident, "event": "extraction",
                    "original_input": extraction_schedule[producer_index]["messages"],
                    "original_response": extraction[producer_index]["raw_response"], "focal_stored_item": item["value"],
                    "producer_index": producer_index})
        assessments = (assess_extraction(folder, inventory, row, ne_items) if include_mcqs else
                       assess_extraction(folder, inventory, row, ne_items, variant=expected_variant,
                                         include_mcqs=False))
        judged, mcqs, ne, qw = (assessments[name] for name in
                              ("triple_judgments", "mcq_answers", "confidence_nemotron", "confidence_qwen"))
        all_results = extraction + judged + mcqs + ne + qw
        summary["technical_counts"] = {"logical_requests": len(all_results),
            "valid": sum(x["status"] == "valid" for x in all_results),
            "technical_retries": sum(x["technical_retry_count"] for x in all_results),
            "raw_transport_records": sum(len(pilot._records(p)) for p in folder.rglob("calls.jsonl")),
            "physical_inference_dispatches": sum(call.get("inference_dispatched") is True
                for p in folder.rglob("calls.jsonl") for call in pilot._records(p)),
            "transport_records_without_inference_dispatch": sum(call.get("inference_dispatched") is not True
                for p in folder.rglob("calls.jsonl") for call in pilot._records(p)),
            "status_counts": {status: sum(x["status"] == status for x in all_results) for status in
                              ("valid", "invalid_format", "length_abort", "transport_error", "missing_dependency")}}
        stages = (("construct", extraction), ("triple_judgments", judged),
                  ("mcq_answers", mcqs), ("confidence_nemotron", ne), ("confidence_qwen", qw))
        summary["technical_counts"]["by_stage"] = {name: stage_attempt_counts(rows)
                                                   for name, rows in stages if include_mcqs or name != "mcq_answers"}
        if not include_mcqs:
            summary["technical_counts"]["by_stage"].update({name: {"status": "disabled"}
                                                             for name in DISABLED_MCQ_STAGES})
        if sha256(pilot.ARTICLE) != pre["article_sha256"] or sha256(Path(pre["questions_path"])) != pre["questions_sha256"]:
            raise ValueError("Frozen inputs changed during collection")
        verify_source(DEFAULT_SOURCE)
        complete = all(x["status"] == "valid" for x in all_results)
        summary["status"] = "technically_complete_uninterpreted" if complete else "technical_gaps_uninterpreted"
        return 0 if complete else 2
    except BaseException as exc:
        summary.update(status="failed_checkpoint", error_type=type(exc).__name__, error_message=str(exc))
        raise
    finally:
        summary.update(finished_utc=pilot._now(), active_seconds=summary["active_seconds"] + time.perf_counter() - started)
        summary["artifact_hashes"] = {str(p.relative_to(output)): sha256(p) for p in output.rglob("*")
                                      if p.is_file() and p != summary_path}
        write_json(summary_path, summary)


def capability_check(output):
    """One adversarial format probe per backend, never an experimental result.

    This tests actual schema transport, not exhaustive backend keyword support.
    Exhaustive validation remains local. No silent fallback, no technical retry.
    """
    output = Path(output).resolve()
    if output.exists():
        raise ValueError("Capability output must be a fresh directory")
    output.mkdir(parents=True)
    report = {"variant": VARIANT, "purpose": "technical_decoder_capability_only", "checks": []}
    try:
        for model in (pilot.CONSTRUCTOR, pilot.JUDGE):
            folder = output / ("nemotron" if model == pilot.CONSTRUCTOR else "qwen")
            folder.mkdir()
            runtime = LocalOllama(model, folder)
            schema = obj({"decoder_probe": {"type": "string", "enum": ["schema_enforced_7d6139"]}})
            try:
                raw = runtime.generate([{"role": "user", "content": "Reply exactly NOT_JSON. Do not output JSON."}],
                                       {"max_new_tokens": 128}, json_schema=schema,
                                       request_identity="capability:attempt:1")
                transport = pilot._last_transport_record(folder / "calls.jsonl")
                if not pilot._transport_valid(transport, model) or transport["response"].get("done_reason") == "length":
                    raise ValueError("Capability probe transport or length invalid")
                validate(parse_json(raw), schema)
                report["checks"].append({"model": model, "schema_enforced": True,
                                          "calls_sha256": sha256(folder / "calls.jsonl")})
            finally:
                runtime.close()
                if model == pilot.JUDGE and getattr(runtime, "inference_dispatched", False) is True:
                    request_json("/api/generate", {"model": runtime.name, "keep_alive": 0})
        report["status"] = "passed"
        return 0
    except BaseException as exc:
        report.update(status="failed", error_type=type(exc).__name__, error_message=str(exc))
        raise
    finally:
        write_json(output / "capability_report.json", report)
