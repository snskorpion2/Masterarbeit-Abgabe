"""One injected source-bound supplementary pass; no launcher or evaluator.

The caller supplies a byte-bound original AS prefix and the matched runtime.
Raw and internally verified views share one candidate draw. Original answers
are never edited. Returned requests and answers are private source material.
"""
from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import inspect
import json
from pathlib import Path

from Experiments.strict_autoschemakg import (
    completion_contracts as native,
    grounded_evidence_v1 as evidence,
    grounded_methods_pilot_v1 as existing,
    grounded_supplement_v2 as glean,
    reliability_v2 as original,
)


PROTOCOL = "fair-as-single-supplement-oct23-v1"
VERIFIER_BATCH_SIZE = 12  # Existing Engine.verify contract, not a new rubric.
MAIN_EVENT_FIELD = native.CATEGORIES["event"]
ORIGINAL_EVENT_FIELD = "event_entity_dict"


def _digest(value):
    return sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
        allow_nan=False, separators=(",", ":")).encode("utf8")).hexdigest()


def code_bindings():
    paths = [Path(__file__), *(Path(module.__file__) for module in
        (native, evidence, existing, glean, original)),
        original.DEFAULT_SOURCE / "atlas_rag/llm_generator/prompt/triple_extraction_prompt.py"]
    return {str(path.resolve()): sha256(path.read_bytes()).hexdigest() for path in paths}


def _main_row(row):
    result = deepcopy(row)
    if ORIGINAL_EVENT_FIELD in result:
        if MAIN_EVENT_FIELD in result:
            raise ValueError("Ambiguous duplicate native event containers")
        result[MAIN_EVENT_FIELD] = result.pop(ORIGINAL_EVENT_FIELD)
    return result


def _output_row(row, original_row):
    result = deepcopy(row)
    if ORIGINAL_EVENT_FIELD in original_row:
        result[ORIGINAL_EVENT_FIELD] = result.pop(MAIN_EVENT_FIELD)
    return result


def _parser_binding(parser):
    path = Path(inspect.getsourcefile(parser)).resolve(strict=True)
    return {"callable": parser.__module__ + "." + parser.__qualname__,
            "path": str(path), "sha256": sha256(path.read_bytes()).hexdigest()}


def validate_prefix(source_bytes, native_row, history, *, native_classifier=original.classify):
    """Validate all original categories before any supplementary dispatch.

    native_classifier may be the caller's explicitly pinned common lossless
    native parser. Its use must not change original wire responses or values.
    This entry accepts one complete native source unit, not a first-chunk proxy.
    """
    return _validate_prefix_messages(source_bytes, native_row, history,
                                     native_classifier=native_classifier)


def _validate_prefix_messages(source_bytes, native_row, history, *,
                              native_classifier, expected_messages=None):
    """Shared structural check; public Original validation never accepts deltas.

    Only the separate fixed SCOPE contract supplies alternative messages. The
    actual history is validated as supplied, never rewritten as Original.
    """
    if type(source_bytes) is not bytes:
        raise TypeError("Exact UTF8 source bytes required")
    text = source_bytes.decode("utf8", errors="strict")
    if not text.strip() or type(native_row) is not dict or type(history) is not dict:
        raise ValueError("Nonempty source, native row and original history required")
    if "original_text" in native_row and native_row["original_text"] != text:
        raise ValueError("Exported original_text differs from exact source unit")
    canonical_row = _main_row(native_row)
    requests, responses = history.get("requests"), history.get("responses")
    if (type(requests) is not list or type(responses) is not list
            or len(requests) != 3 or len(responses) != 3):
        raise ValueError("Exactly three complete original category requests/responses required; "
                         "multi-chunk histories require a separate complete-document contract")
    if expected_messages is None:
        expected_messages = original.native_extraction_prompts(text)
    if type(expected_messages) is not list or len(expected_messages) != 3:
        raise ValueError("Exactly three bound category message sets required")
    ids = []
    for category, messages, query, response in zip(
            original.CATEGORIES, expected_messages, requests, responses):
        if (type(query) is not dict or query.get("kind") != "extraction"
                or query.get("category") != category or not isinstance(query.get("request_id"), str)
                or not query["request_id"].strip() or query.get("messages") != messages
                or type(response) is not dict or response.get("status") != "valid"
                or response.get("request_id") != query["request_id"]
                or type(response.get("raw_response")) is not str):
            raise ValueError("Original source, prompt, category or response identity differs")
        field = native.CATEGORIES[category]
        values = canonical_row.get(field)
        if type(values) is not list:
            raise ValueError("Complete native category lists required")
        for value in values:
            native._native_value(category, value)
        parsed = native_classifier(deepcopy(query), response["raw_response"])
        if _digest(parsed) != _digest(values) or _digest(response.get("parsed")) != _digest(values):
            raise ValueError("Original raw/parsed response differs from native inventory")
        ids.append(query["request_id"])
    if len(set(ids)) != len(ids):
        raise ValueError("Unique original request IDs required")
    # Validate optional occurrence sidecar and all source spans without rewriting S0.
    evidence.merge_native(canonical_row, [])
    catalog = evidence.catalog(text)
    evidence.validate_catalog(catalog, text)
    return text, catalog


class _Calls:
    """Bounded transparent adapter; a failure never triggers another dispatch."""

    def __init__(self, runtime, parameters, maximum):
        self.runtime, self.parameters, self.maximum = runtime, deepcopy(parameters), maximum
        self.ledger, self.failures, self.halted = [], [], None

    def call(self, query, *, judge=False, schema=evidence.schema_for,
             classifier=evidence.classify):
        if self.halted is not None or len(self.ledger) >= self.maximum:
            status = self.halted or "request_limit"
            return {"status": "blocked_after_" + status, "parsed": None,
                    "raw_response": "", "blocked_without_dispatch": True}
        query = deepcopy(query)
        original_parameters = deepcopy(query.get("parameters", {}))
        query["parameters"] = deepcopy(self.parameters)
        captured = deepcopy(query)
        entry = {"query": captured, "internal_verification": judge,
                 "request_sha256": _digest(captured),
                 "original_method_parameters": original_parameters,
                 "actual_declared_parameters": deepcopy(self.parameters)}
        self.ledger.append(entry)  # Reserve the slot even if callback raises.
        try:
            result = deepcopy(self.runtime.call(deepcopy(query), judge=judge,
                schema=schema, classifier=classifier))
        except Exception as error:
            result = {"status": "unknown_execution", "parsed": None,
                "raw_response": "", "exception_class": type(error).__name__}
        entry["original_result"] = deepcopy(result)
        if type(result) is not dict or type(result.get("status")) is not str:
            result = {"status": "unknown_execution", "parsed": None, "raw_response": ""}
        elif result["status"] == "valid":
            try:
                if (type(result.get("raw_response")) is not str
                        or _digest(classifier(query, result["raw_response"])) != _digest(result.get("parsed"))):
                    raise ValueError("Raw and parsed callback values differ")
            except (ValueError, TypeError, KeyError, IndexError):
                result["status"] = "invalid_format"
        entry["validated_status"] = result["status"]
        if result["status"] != "valid":
            self.halted = result["status"]
            self.failures.append({"request_id": captured["request_id"], "status": self.halted})
        return result

    def verify(self, candidates, catalog, prefix):
        # The existing request builder, categorical gate, batch size and handling
        # of technical unknowns remain visible under their original code pins.
        return existing.Engine.verify(self, candidates, catalog, prefix)


def supplement(source_bytes, native_row, history, runtime, *, parameters,
               max_calls=12, native_classifier=original.classify):
    """Return S0, raw A, and verified A from one pass per native category.

    runtime.call is injected and owns physical receipts, matched constructor
    identity/last-mile settings and retry policy. This module never loads keys,
    starts processes, dispatches directly or conducts independent evaluation.
    """
    text, catalog = validate_prefix(source_bytes, native_row, history,
                                    native_classifier=native_classifier)
    if (not callable(getattr(runtime, "call", None)) or type(parameters) is not dict
            or type(parameters.get("max_new_tokens")) is not int
            or parameters["max_new_tokens"] <= 0 or type(max_calls) is not int
            or not 3 <= max_calls <= 12):
        raise ValueError("Explicit bounded runtime and actual common parameters required")
    _digest(parameters)  # Reject nonfinite/nonserializable settings before dispatch.
    source_hash = sha256(source_bytes).hexdigest()
    prefix_hash = _digest(history)
    base_hash = _digest(native_row)
    bindings = code_bindings()  # Freeze before the first callback can dispatch.
    parser_binding = _parser_binding(native_classifier)
    bindings[parser_binding["path"]] = parser_binding["sha256"]
    canonical_row = _main_row(native_row)
    calls = _Calls(runtime, parameters, max_calls)
    candidates, rounds = [], []
    for category, query, response in zip(original.CATEGORIES,
                                       history["requests"], history["responses"]):
        conversation = deepcopy(query["messages"]) + [
            {"role": "assistant", "content": response["raw_response"]}]
        request = glean.glean_request(category, conversation, catalog, 1, max_rounds=1)
        result = calls.call(request)
        rounds.append({"category": category, "request_id": request["request_id"],
                       "status": result["status"]})
        if result["status"] != "valid":
            break
        candidates.extend(evidence.assign_candidates(result["parsed"]["candidates"],
            category, "source:" + source_hash + ":" + request["request_id"]))
    draw_complete = len(rounds) == 3 and all(r["status"] == "valid" for r in rounds)
    verification = {"accepted": [], "audit": [], "candidates": deepcopy(candidates),
                    "verification_failures": []}
    required_batches = (len(candidates) + VERIFIER_BATCH_SIZE - 1) // VERIFIER_BATCH_SIZE
    budget_sufficient = required_batches <= max_calls - len(calls.ledger)
    if draw_complete and budget_sufficient:
        verification = calls.verify(deepcopy(candidates), deepcopy(catalog), "A")
    elif draw_complete:
        calls.failures.append({"request_id": "A:verify", "status": "request_limit",
            "required_batches": required_batches, "remaining_calls": max_calls - len(calls.ledger)})
    complete = draw_complete and budget_sufficient and not calls.failures
    raw = evidence.merge_native(canonical_row, deepcopy(candidates))
    checked = evidence.merge_native(canonical_row, deepcopy(verification["accepted"]))
    return {"protocol": PROTOCOL, "status": "finished" if complete else
            "unknown_execution" if calls.halted == "unknown_execution" else "incomplete",
        "complete": complete, "source_sha256": source_hash, "source_bytes": len(source_bytes),
        "prefix_sha256": prefix_hash, "baseline_sha256": base_hash,
        "methods": ["native_AS_prefix", "A_single_pass", "existing_internal_source_gate"],
        "disabled": ["C", "A_chunk", "B", "K", "R", "independent_evaluation"],
        "parameters": deepcopy(parameters), "max_extra_callback_calls": max_calls,
        "actual_extra_callback_calls": len(calls.ledger),
        "physical_request_count": None, "physical_usage": None,
        "physical_accounting_owner": "injected runtime receipts; callbacks are not physical attempts",
        "draw_complete": draw_complete, "rounds": rounds, "candidates": deepcopy(candidates),
        "verification": deepcopy(verification), "technical_failures": deepcopy(calls.failures),
        "pending_verification_ids": [c["id"] for c in candidates
            if c["id"] not in {a["id"] for a in verification["audit"]
                               if not a.get("technical_verification_failure")}],
        "views": {"S0": deepcopy(native_row),
                  "AS_A_raw": _output_row(raw["native_row"], native_row),
                  "AS_A_verified": _output_row(checked["native_row"], native_row)},
        "native_field_bridge": {"input_event_field": ORIGINAL_EVENT_FIELD
            if ORIGINAL_EVENT_FIELD in native_row else MAIN_EVENT_FIELD,
            "internal_event_field": MAIN_EVENT_FIELD, "output_matches_input": True,
            "changes_native_values": False},
        "native_parser_binding": parser_binding,
        "view_complete": {"S0": True, "AS_A_raw": draw_complete, "AS_A_verified": complete},
        "internal_verifier_contract": {"request_builder": "grounded_evidence_v1.verifier_request",
            "runner": "grounded_methods_pilot_v1.Engine.verify", "batch_size": VERIFIER_BATCH_SIZE,
            "acceptance": "existing bound entire-claim supported gate; model-verified, not gold",
            "parameters": deepcopy(parameters), "independent_evaluation": False},
        "private_source_bearing": True, "semantic_quality_measured": False,
        "ledger": deepcopy(calls.ledger), "code_bindings": bindings,
        "prefix_mutated": _digest(history) != prefix_hash or _digest(native_row) != base_hash}
