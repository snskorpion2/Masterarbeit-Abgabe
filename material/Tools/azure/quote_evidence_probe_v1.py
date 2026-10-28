"""Isolated exact-quote-only format probe; CPU prepare/verify, opt-in execute.

Same first original EV/EE/VV controls, semantic instructions and source text.
Only evidence delivery changes: the model copies quotes, code locates exactly
one overlapping-aware occurrence, then the unchanged original validator runs.
No semantic repair, retries, thinking switch, judge admission or quality score.
"""
from __future__ import annotations

import argparse
from collections import Counter
from copy import deepcopy
from hashlib import sha256
from pathlib import Path
import time
from urllib.error import HTTPError
from Tools.azure import accounting

from Tools.azure import output_budget_probe_v2 as base

HERE = Path(__file__).resolve()
TEST = HERE.parents[1] / "tests/test_azure_quote_evidence_probe_v1.py"
PREVIOUS_OUTPUT = base.old.MAIN_ROOT / "Experiments/results/abschluss_azure_kimi_output_budget_oct12_v2"
PROTOCOL = "azure-kimi-exact-quote-evidence:v1"
LIMITS = {**base.LIMITS, "max_HTTP_requests": 4, "control_calls": 3,
          "output_tokens_per_request": 4096, "max_output_tokens_total": 13312}
FORMAT_PREFIX = "Output format contract only. This is not source evidence or a reference answer. Return one JSON object conforming exactly to this schema: "
OLD_POSITION_INSTRUCTION = ("Copy evidence verbatim with zero-based, end-exclusive Unicode character positions in the source. "
                            "Evidence positions demonstrate traceability, not semantic correctness.")
QUOTE_INSTRUCTION = ("Copy evidence verbatim as exact quotes from the source; do not compute or return character positions. "
                     "Exact quotes demonstrate traceability, not semantic correctness.")
canonical, digest, unlinked, FILES = base.canonical, base.digest, base.unlinked, base.FILES


def quote_schema(support, identifier):
    schema = deepcopy(support.response_schema(identifier))
    item = schema["properties"]["evidence"]["items"]
    item["properties"] = {"quote": item["properties"]["quote"]}
    item["required"] = ["quote"]
    return schema


def quote_payload(support, task, old_payload):
    payload = deepcopy(old_payload)
    messages = payload["messages"]
    original_schema = canonical(support.response_schema(task["request_id"])).decode()
    if (len(messages) != 3 or messages[0] != {"role": "system", "content": support.SYSTEM_PROMPT}
            or messages[1] != {"role": "system", "content": FORMAT_PREFIX + original_schema}
            or support.SYSTEM_PROMPT.count(OLD_POSITION_INSTRUCTION) != 1):
        raise ValueError("Exact original semantic prompt and format contract required")
    messages[0]["content"] = support.SYSTEM_PROMPT.replace(OLD_POSITION_INSTRUCTION, QUOTE_INSTRUCTION)
    messages[1]["content"] = FORMAT_PREFIX + canonical(quote_schema(support, task["request_id"])).decode()
    payload["max_completion_tokens"] = 4096
    return payload


def prepare(source_plan, code_root, run_output, env_path=base.old.v1.probe.DEFAULT_ENV):
    original, pairs, private, human, old_payloads = base.prepare(source_plan, code_root, run_output, env_path)
    support, _, _ = base.old.v1.common.backend(code_root)
    selected = [deepcopy(pairs[i]["task"]) for i in (0, 2, 4)]
    tasks = [{"task": task, "output_cap": 4096, "control_ordinal": i} for i, task in enumerate(selected)]
    payloads = [deepcopy(old_payloads[0]), *[quote_payload(support, task, old_payloads[i + 1])
                for i, task in zip((0, 2, 4), selected)]]
    if any(len(canonical(p)) + 256 > 16384 or base.old.reservation(p) >= 20000 for p in payloads):
        raise ValueError("Input or rolling-minute reservation exceeds unchanged limits")
    worst = (4 * 16384 * 0.95 + 13312 * 4.0) / 1e6
    if worst >= 2 or original["budget_reservation"]["pilot_cap_USD"] < 9:
        raise ValueError("Previous seven dollars plus new two dollars must fit the existing pilot")
    body = {k: v for k, v in original.items() if k not in ("plan_sha256", "paired_order")}
    body.update(protocol=PROTOCOL, method="exact_quote_only_unique_original_locator", limits=LIMITS,
        control_count=3, original_message_texts_preserved=False, semantic_instructions_preserved_except_evidence_format=True,
        preparation_adapter_v2_plan_sha256=original["plan_sha256"],
        source_format_message_sha256=original["format_message_sha256"],
        format_message_sha256=[sha256(p["messages"][1]["content"].encode()).hexdigest() for p in payloads[1:]],
        effective_system_prompt_sha256=sha256(payloads[1]["messages"][0]["content"].encode()).hexdigest(),
        probe_order="Same preselected first original EV/EE/VV cases, one fresh request each, fixed 4096 output.",
        public_tasks_sha256=digest(tasks), ordered_payloads_sha256=digest(payloads),
        token_reservations=[base.old.reservation(p) for p in payloads],
        own_code_and_tests=[*original["own_code_and_tests"], base.old.v1.common.binding(HERE), base.old.v1.common.binding(TEST)],
        previous_evidence_bindings=[*original["previous_evidence_bindings"], *[base.old.v1.common.binding(PREVIOUS_OUTPUT / n)
            for n in ("frozen_plan.json", "summary.json")]],
        evidence_contract={"model_fields": ["quote"], "quote_changed": False, "matching": "unique_exact_overlap_aware",
            "zero_or_multiple_occurrences": "technical_invalid", "canonical_fields": ["start", "end", "quote"],
            "unchanged_original_validator": True, "semantic_correctness_verified": False},
        budget_reservation={**original["budget_reservation"], "max_output_tokens": 13312,
            "worst_case_public_list_price_USD": worst, "previous_outstanding_reserved_USD": 7.0,
            "previous_output_probe_v2_reserved_USD": 2.0, "total_conservative_reservation_USD": 9.0,
            "previous_known_public_list_price_estimates_USD": [0.0004769, 0.07987842, 0.05847813, 0.13005269]})
    return {**body, "plan_sha256": digest(body)}, tasks, private, human, payloads


def write_preparation(prepared, output):
    plan = prepared[0]
    if prepare(plan["source_plan"], plan["code_root"], plan["execution_output"], plan["environment_path"]) != prepared:
        raise ValueError("Preparation changed")
    support, _, _ = base.old.v1.common.backend(plan["code_root"])
    target, run = support.transport._fresh(output), support.transport._fresh(plan["execution_output"])
    source = unlinked(plan["source_plan"]).parent
    for a, b in ((target, source), (run, source), (target, run)):
        if a.is_relative_to(b) or b.is_relative_to(a): raise ValueError("Evidence directories must not overlap")
    target.mkdir()
    for name, value in zip(("plan.json", *FILES), prepared): support._publish(target / name, value)
    return {"status": "prepared_not_started", "plan_sha256": plan["plan_sha256"], "model_calls": 0}


def verify(plan_path):
    path = unlinked(plan_path)
    plan = base.old.v1.common.strict_plan(path.read_bytes())
    if plan.get("protocol") != PROTOCOL or plan.get("plan_sha256") != digest({k: v for k, v in plan.items() if k != "plan_sha256"}):
        raise ValueError("Exact sealed quote-only plan required")
    actual = (plan, *[base.old.v1.common.strict_plan(unlinked(path.parent / n).read_bytes()) for n in FILES])
    if prepare(plan["source_plan"], plan["code_root"], plan["execution_output"], plan["environment_path"]) != actual:
        raise ValueError("Frozen source/resource/previous evidence/prompt/schema/code or limits changed")
    return actual


def locate_quotes(support, task, raw):
    value = support.strict_json(raw)
    if not isinstance(value, dict) or set(value) != {"claim_id", "status", "reason", "evidence"}:
        raise ValueError("quote_response_structure_invalid")
    evidence = value["evidence"]
    if not isinstance(evidence, list) or len(evidence) > 2: raise ValueError("quote_evidence_structure_invalid")
    result, spans = deepcopy(value), []
    source = task["source"]["text"]
    for item in evidence:
        if (not isinstance(item, dict) or set(item) != {"quote"} or not isinstance(item["quote"], str)
                or not 1 <= len(item["quote"]) <= 320): raise ValueError("quote_evidence_structure_invalid")
        quote = item["quote"]
        start = source.find(quote)
        if start < 0: raise ValueError("exact_quote_not_found")
        if source.find(quote, start + 1) >= 0: raise ValueError("exact_quote_ambiguous")
        spans.append({"quote": quote, "start": start, "end": start + len(quote)})
    result["evidence"] = spans
    return result


def parse_quote_response(support, task, raw, *, execution_confirmed):
    if execution_confirmed is not True:
        return {**support.parse_response(task, raw, execution_confirmed=False), "quote_locator_applied": False}
    try:
        located = locate_quotes(support, task, raw)
    except (ValueError, TypeError, KeyError, UnicodeError) as exc:
        errors = {"quote_response_structure_invalid", "quote_evidence_structure_invalid", "exact_quote_not_found", "exact_quote_ambiguous"}
        error = str(exc) if str(exc) in errors else "quote_response_invalid_JSON"
        return {**support.parse_response(task, None, execution_confirmed=True), "technical_error": error,
                "quote_locator_applied": False}
    parsed = support.parse_response(task, canonical(located), execution_confirmed=True)
    return {**parsed, "quote_locator_applied": True, "canonical_response_sha256": digest(located)}


def execute(plan_path, *, approved_plan_sha256, wire=base.azure_wire, clock=time.monotonic, sleep=time.sleep):
    plan, tasks, private, human, payloads = verify(plan_path)
    if approved_plan_sha256 != plan["plan_sha256"]: raise ValueError("Exact reviewed plan required before HTTP")
    support, _, Journal = base.old.v1.common.backend(plan["code_root"])
    config = base.old.v1.probe.load_config(plan["environment_path"])
    target = support.transport._fresh(plan["execution_output"])
    target.mkdir()
    start, history, receipts, observations = clock(), [], [], []
    deadline, failure, smoke, after = start + 900, None, False, False
    labels = {r["request_id"]: r["assessment_only"]["expected_supported"] for r in private["mapping"]}
    for name, value in zip(("frozen_plan.json", *FILES), (plan, tasks, private, human, payloads)): support._publish(target / name, value)
    journal = Journal(target / "ledger")
    with journal.locked():
        journal.record("run_start", plan["plan_sha256"], limits=LIMITS, reserved_USD=2.0, total_retained_reservation_USD=9.0)
        try:
            for ordinal, payload in enumerate(payloads):
                if ordinal >= 4 or not base.old.v1.wait_for_slot(history, base.old.reservation(payload), deadline, clock=clock, sleep=sleep):
                    failure = "dispatch_budget_exhausted"
                    break
                task, cap = tasks[ordinal - 1]["task"] if ordinal else None, payload["max_completion_tokens"]
                identifier = task["request_id"] if task else "source_free_smoke"
                key, begin = digest([plan["plan_sha256"], ordinal, identifier, cap]), clock()
                support._publish(target / f"HTTP/{ordinal:04d}-request.json", payload)
                journal.record("request_intent", key, ordinal=ordinal, request_id=identifier, request_sha256=digest(payload))
                receipt = {"ordinal": ordinal, "request_id": identifier, "output_cap": cap, "POST_attempts": 0, "physical_dispatch_performed": False, "response_archive_complete": False,
                    "unknown_execution": True, "metering_complete": False, "response_body_sha256": None,
                    "http_status": None, "list_price_estimate_USD": None, "actual_cost_USD": None,
                    "provider_runtime_seconds": None, "hardware_usage": None}
                try:
                    remaining = deadline - clock()
                    if remaining <= 0: failure = "dispatch_budget_exhausted"; break
                    receipt.update(timeout_seconds=min(120, remaining), dispatch_UTC=base.old.v1.probe._utc_timestamp())
                    history.append((clock(), base.old.reservation(payload)))
                    journal.record("dispatch", key, **receipt)
                    receipt.update(POST_attempts=1, physical_dispatch_performed=True)
                    try: status, raw = wire(config, payload, timeout=receipt["timeout_seconds"])
                    except HTTPError as exc: status, raw = exc.code, exc.read(262145)
                    receipt["http_status"] = status if type(status) is int else None
                    accounting.book(receipt, raw, config, payload["max_completion_tokens"],
                        max_bytes=LIMITS["max_response_bytes"], strict_json=base.old.v1.probe._strict_json, price_estimate=base.old.v1.price_estimate)
                    if isinstance(raw, bytes): receipt["response_body_sha256"] = sha256(raw).hexdigest()
                    if type(status) is not int or status != 200:
                        receipt.update(base.old.safe_error(status, raw)); failure = receipt["error_category"]; break
                    text, details = base.provider_response(raw, config, cap)
                    receipt.update(details)
                    with (target / f"HTTP/{ordinal:04d}-success-body.json").open("xb") as stream: stream.write(raw)
                    receipt["response_archive_complete"] = True
                    if not details["metering_complete"] or not details["completion_within_requested_cap"]:
                        failure = "provider_meter_missing_inconsistent_or_cap_exceeded"; break
                    if not receipt.get("provider_completion_confirmed"):
                        failure = "provider_completion_unconfirmed"
                        break
                    if details["provider_model"] != base.old.v1.probe.MODEL: failure = "provider_model_differs"; break
                    if details["provider_usage"]["prompt_tokens"] > len(canonical(payload)) + 256:
                        failure = "conservative_input_reservation_exceeded"; break
                    cleaned, bridges = base.old.v1.common.unwrap_format(text)
                    receipt["visible_content_chars"] = len(text) if isinstance(text, str) else None
                    if not task:
                        smoke = details["finish_reason"] == "stop" and base.old.v1.common.smoke_ready(support.strict_json(cleaned))
                        if not smoke: failure = "source_free_smoke_invalid"; break
                    else:
                        parsed = parse_quote_response(support, task, cleaned, execution_confirmed=details["finish_reason"] == "stop")
                        if details["finish_reason"] != "stop": parsed["technical_error"] = "provider_finish_not_stop"
                        parsed.update(axis=task["axis"], output_cap=cap, wrapper_bridges=bridges,
                            provider_finish_reason=details["finish_reason"], expected_supported_provisional=labels[identifier],
                            matches_provisional_reference=((parsed["status"] == "supported") == labels[identifier])
                            if parsed["semantic_judgment_available"] else None)
                        observations.append(parsed)
                except Exception: failure = "transport_or_response_unknown"; break
                finally:
                    accounting.finish_local(receipt)
                    receipt.update(finish_UTC=base.old.v1.probe._utc_timestamp(), client_elapsed_seconds=max(0.0, clock() - begin))
                    receipts.append(receipt)
                    support._publish(target / f"HTTP/{ordinal:04d}-receipt.json", receipt)
                    journal.record("request_terminal", key, **receipt)
            verify(plan_path)
            after = True
        except Exception: failure = "post_binding_or_runner_failure"
        summary = {"protocol": PROTOCOL, "method": plan["method"], "plan_sha256": plan["plan_sha256"],
            "diagnostic_execution_complete": failure is None and smoke and after and len(observations) == 3,
            "failure": failure, "HTTP_requests": sum(r["POST_attempts"] for r in receipts), "control_responses": len(observations),
            "unknown_execution_count": sum(r["unknown_execution"] for r in receipts if r["POST_attempts"]),
            "technical_valid_controls": sum(o["semantic_judgment_available"] for o in observations),
            "technical_error_counts": dict(Counter(o.get("technical_error") for o in observations if not o["semantic_judgment_available"])),
            "actual_cost_USD": None, "provider_runtime_seconds": None, "hardware_usage": None,
            "client_elapsed_seconds": max(0.0, clock() - start), "client_time_is_not_provider_time": True,
            "binding_verification_after": after, "automatic_retries": 0, "judge_admitted": False,
            "accuracy": None, "F1": None, "system_MINE_score": None}
        summary.update(accounting.totals(receipts))
        journal.record("run_terminal", plan["plan_sha256"], summary_sha256=digest(summary))
        summary["ledger_terminal_sha256"] = digest(journal.events()[-1])
        for name, value in (("responses.json", observations), ("HTTP_receipts.json", receipts), ("summary.json", summary)):
            support._publish(target / name, value)
    return summary


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group(required=True)
    for mode in ("prepare", "verify", "execute"): modes.add_argument("--" + mode, action="store_true")
    for name in ("source-plan", "code-root", "run-output", "output", "plan"): parser.add_argument("--" + name, type=Path)
    parser.add_argument("--env", type=Path, default=base.old.v1.probe.DEFAULT_ENV)
    parser.add_argument("--approved-plan-sha256")
    args = parser.parse_args(argv)
    try:
        if args.prepare:
            if any(v is None for v in (args.source_plan, args.code_root, args.run_output, args.output)): raise ValueError("Paths required")
            result = write_preparation(prepare(args.source_plan, args.code_root, args.run_output, args.env), args.output)
        elif args.verify: result = {"verified": True, "model_calls": 0, "plan_sha256": verify(args.plan)[0]["plan_sha256"]}
        else: result = execute(args.plan, approved_plan_sha256=args.approved_plan_sha256)
    except Exception: result = {"protocol": PROTOCOL, "status": "local_guard_failure", "secret_or_error_body_published": False}
    print(canonical(result).decode())
    return int(result.get("status") == "local_guard_failure" or bool(result.get("failure")))


if __name__ == "__main__": raise SystemExit(main())
