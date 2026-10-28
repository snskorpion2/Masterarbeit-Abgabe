"""All 30 original known controls, fixed 4096, exact-quote delivery only.

CPU preparation/verification; explicit sealed-plan execution only. One smoke
and thirty fresh controls, no retries, admission, F1 or human-gold claim. The
unchanged V1 quote locator and original claim validator are reused, not edited.
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

from Tools.azure import quote_evidence_probe_v1 as quote

HERE = Path(__file__).resolve()
TEST = HERE.parents[1] / "tests/test_azure_quote_controls_v2.py"
PREVIOUS_QUOTE = quote.base.old.MAIN_ROOT / "Experiments/results/abschluss_azure_kimi_quote_evidence_oct12_v1"
PROTOCOL = "azure-kimi-known-controls-exact-quote:v2"
LIMITS = {**quote.LIMITS, "max_HTTP_requests": 31, "control_calls": 30,
          "dispatch_deadline_seconds": 1800, "max_output_tokens_total": 123904}
canonical, digest, unlinked, FILES = quote.canonical, quote.digest, quote.unlinked, quote.FILES


def prepare(source_plan, code_root, run_output, env_path=quote.base.old.v1.probe.DEFAULT_ENV):
    inherited, _, private, human, _ = quote.prepare(source_plan, code_root, run_output, env_path)
    original, original_tasks, original_private, original_human, original_payloads = quote.base.old.v1.prepare(
        source_plan, code_root, run_output, env_path)
    support, _, _ = quote.base.old.v1.common.backend(code_root)
    if (len(original_tasks) != 30 or len(original_payloads) != 31 or original_private != private
            or original_human != human or len({t["request_id"] for t in original_tasks}) != 30
            or Counter(t["axis"] for t in original_tasks) != {"EE": 10, "EV": 10, "VV": 10}):
        raise ValueError("All original thirty unique controls and private reference separation required")
    tasks = [{"task": deepcopy(t), "output_cap": 4096, "control_ordinal": i} for i, t in enumerate(original_tasks)]
    payloads = [deepcopy(original_payloads[0]), *[quote.quote_payload(support, t, p)
                for t, p in zip(original_tasks, original_payloads[1:])]]
    if any(len(canonical(p)) + 256 > 16384 or quote.base.old.reservation(p) >= 20000 for p in payloads):
        raise ValueError("Unchanged conservative input/minute limits exceeded")
    worst = (31 * 16384 * 0.95 + 123904 * 4.0) / 1e6
    if worst >= 2 or inherited["budget_reservation"]["pilot_cap_USD"] < 11:
        raise ValueError("Retained nine plus new two dollars must fit the existing pilot")
    body = {k: v for k, v in inherited.items() if k != "plan_sha256"}
    body.update(protocol=PROTOCOL, limits=LIMITS, control_count=30,
        source_control_inventory_count=30, original_model_input_order_preserved=True,
        selection_rule="All thirty frozen original controls in their original order, no label/outcome filtering.",
        probe_order="Original thirty-control order, fixed 4096 output each; unchanged ready smoke first.",
        selected_controls=[{"request_id": t["request_id"], "axis": t["axis"]} for t in original_tasks],
        preparation_quote_adapter_v1_plan_sha256=inherited["plan_sha256"],
        preparation_full_control_adapter_v1_plan_sha256=original["plan_sha256"],
        public_tasks_sha256=digest(tasks), ordered_payloads_sha256=digest(payloads),
        source_format_message_sha256=original["format_message_sha256"],
        format_message_sha256=[sha256(p["messages"][1]["content"].encode()).hexdigest() for p in payloads[1:]],
        token_reservations=[quote.base.old.reservation(p) for p in payloads],
        own_code_and_tests=[*inherited["own_code_and_tests"], quote.base.old.v1.common.binding(HERE), quote.base.old.v1.common.binding(TEST)],
        previous_evidence_bindings=[*inherited["previous_evidence_bindings"], *[quote.base.old.v1.common.binding(PREVIOUS_QUOTE / n)
            for n in ("frozen_plan.json", "summary.json")]],
        budget_reservation={**inherited["budget_reservation"], "max_output_tokens": 123904,
            "worst_case_public_list_price_USD": worst, "previous_outstanding_reserved_USD": 9.0,
            "previous_quote_probe_v1_reserved_USD": 2.0, "total_conservative_reservation_USD": 11.0,
            "previous_known_public_list_price_estimates_USD": [0.0004769, 0.07987842, 0.05847813, 0.13005269, 0.02260687]})
    return {**body, "plan_sha256": digest(body)}, tasks, private, human, payloads


def write_preparation(prepared, output):
    plan = prepared[0]
    if prepare(plan["source_plan"], plan["code_root"], plan["execution_output"], plan["environment_path"]) != prepared:
        raise ValueError("Preparation changed")
    support, _, _ = quote.base.old.v1.common.backend(plan["code_root"])
    target, run = support.transport._fresh(output), support.transport._fresh(plan["execution_output"])
    source = unlinked(plan["source_plan"]).parent
    for a, b in ((target, source), (run, source), (target, run)):
        if a.is_relative_to(b) or b.is_relative_to(a): raise ValueError("Evidence directories must not overlap")
    target.mkdir()
    for name, value in zip(("plan.json", *FILES), prepared): support._publish(target / name, value)
    return {"status": "prepared_not_started", "plan_sha256": plan["plan_sha256"], "model_calls": 0}


def verify(plan_path):
    path = unlinked(plan_path)
    plan = quote.base.old.v1.common.strict_plan(path.read_bytes())
    if plan.get("protocol") != PROTOCOL or plan.get("plan_sha256") != digest({k: v for k, v in plan.items() if k != "plan_sha256"}):
        raise ValueError("Exact sealed full-control quote plan required")
    actual = (plan, *[quote.base.old.v1.common.strict_plan(unlinked(path.parent / n).read_bytes()) for n in FILES])
    if prepare(plan["source_plan"], plan["code_root"], plan["execution_output"], plan["environment_path"]) != actual:
        raise ValueError("Frozen source/resource/previous evidence/selection/prompt/schema/code or limits changed")
    return actual


def execute(plan_path, *, approved_plan_sha256, wire=quote.base.azure_wire, clock=time.monotonic, sleep=time.sleep):
    plan, tasks, private, human, payloads = verify(plan_path)
    if approved_plan_sha256 != plan["plan_sha256"]: raise ValueError("Exact reviewed plan required before HTTP")
    support, _, Journal = quote.base.old.v1.common.backend(plan["code_root"])
    config = quote.base.old.v1.probe.load_config(plan["environment_path"])
    target = support.transport._fresh(plan["execution_output"])
    target.mkdir()
    start, history, receipts, observations = clock(), [], [], []
    deadline, failure, smoke, after = start + 1800, None, False, False
    labels = {r["request_id"]: r["assessment_only"]["expected_supported"] for r in private["mapping"]}
    for name, value in zip(("frozen_plan.json", *FILES), (plan, tasks, private, human, payloads)): support._publish(target / name, value)
    journal = Journal(target / "ledger")
    with journal.locked():
        journal.record("run_start", plan["plan_sha256"], limits=LIMITS, reserved_USD=2.0, total_retained_reservation_USD=11.0)
        try:
            for ordinal, payload in enumerate(payloads):
                if ordinal >= 31 or not quote.base.old.v1.wait_for_slot(history, quote.base.old.reservation(payload), deadline, clock=clock, sleep=sleep):
                    failure = "dispatch_budget_exhausted"; break
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
                    receipt.update(timeout_seconds=min(120, remaining), dispatch_UTC=quote.base.old.v1.probe._utc_timestamp())
                    history.append((clock(), quote.base.old.reservation(payload)))
                    journal.record("dispatch", key, **receipt)
                    receipt.update(POST_attempts=1, physical_dispatch_performed=True)
                    try: status, raw = wire(config, payload, timeout=receipt["timeout_seconds"])
                    except HTTPError as exc: status, raw = exc.code, exc.read(262145)
                    receipt["http_status"] = status if type(status) is int else None
                    accounting.book(receipt, raw, config, payload["max_completion_tokens"],
                        max_bytes=LIMITS["max_response_bytes"], strict_json=quote.base.old.v1.probe._strict_json, price_estimate=quote.base.old.v1.price_estimate)
                    if isinstance(raw, bytes): receipt["response_body_sha256"] = sha256(raw).hexdigest()
                    if type(status) is not int or status != 200:
                        receipt.update(quote.base.old.safe_error(status, raw)); failure = receipt["error_category"]; break
                    text, details = quote.base.provider_response(raw, config, cap)
                    receipt.update(details)
                    with (target / f"HTTP/{ordinal:04d}-success-body.json").open("xb") as stream: stream.write(raw)
                    receipt["response_archive_complete"] = True
                    if not details["metering_complete"] or not details["completion_within_requested_cap"]:
                        failure = "provider_meter_missing_inconsistent_or_cap_exceeded"; break
                    if not receipt.get("provider_completion_confirmed"):
                        failure = "provider_completion_unconfirmed"
                        break
                    if details["provider_model"] != quote.base.old.v1.probe.MODEL: failure = "provider_model_differs"; break
                    if details["provider_usage"]["prompt_tokens"] > len(canonical(payload)) + 256:
                        failure = "conservative_input_reservation_exceeded"; break
                    cleaned, bridges = quote.base.old.v1.common.unwrap_format(text)
                    receipt["visible_content_chars"] = len(text) if isinstance(text, str) else None
                    if not task:
                        smoke = details["finish_reason"] == "stop" and quote.base.old.v1.common.smoke_ready(support.strict_json(cleaned))
                        if not smoke: failure = "source_free_smoke_invalid"; break
                    else:
                        parsed = quote.parse_quote_response(support, task, cleaned, execution_confirmed=details["finish_reason"] == "stop")
                        if details["finish_reason"] != "stop": parsed["technical_error"] = "provider_finish_not_stop"
                        parsed.update(axis=task["axis"], output_cap=cap, wrapper_bridges=bridges,
                            provider_finish_reason=details["finish_reason"], expected_supported_provisional=labels[identifier],
                            matches_provisional_reference=((parsed["status"] == "supported") == labels[identifier])
                            if parsed["semantic_judgment_available"] else None)
                        observations.append(parsed)
                except Exception: failure = "transport_or_response_unknown"; break
                finally:
                    accounting.finish_local(receipt)
                    receipt.update(finish_UTC=quote.base.old.v1.probe._utc_timestamp(), client_elapsed_seconds=max(0.0, clock() - begin))
                    receipts.append(receipt)
                    support._publish(target / f"HTTP/{ordinal:04d}-receipt.json", receipt)
                    journal.record("request_terminal", key, **receipt)
            verify(plan_path)
            after = True
        except Exception: failure = "post_binding_or_runner_failure"
        summary = {"protocol": PROTOCOL, "method": plan["method"], "plan_sha256": plan["plan_sha256"],
            "diagnostic_execution_complete": failure is None and smoke and after and len(observations) == 30,
            "failure": failure, "HTTP_requests": sum(r["POST_attempts"] for r in receipts), "control_responses": len(observations),
            "not_attempted_controls": 30 - sum(bool(r["POST_attempts"]) for r in receipts if r["ordinal"] > 0),
            "unknown_execution_count": sum(r["unknown_execution"] for r in receipts if r["POST_attempts"]),
            "technical_valid_controls": sum(o["semantic_judgment_available"] for o in observations),
            "technical_valid_by_axis": {a: sum(o["axis"] == a and o["semantic_judgment_available"] for o in observations) for a in ("EE", "EV", "VV")},
            "technical_error_counts": dict(Counter(o.get("technical_error") for o in observations if not o["semantic_judgment_available"])),
            "matches_provisional_reference_count": sum(o["matches_provisional_reference"] is True for o in observations),
            "actual_cost_USD": None, "provider_runtime_seconds": None, "hardware_usage": None,
            "client_elapsed_seconds": max(0.0, clock() - start), "client_time_is_not_provider_time": True,
            "binding_verification_after": after, "automatic_retries": 0, "judge_admitted": False,
            "human_gold": False, "known_previously_used_AI_provisional_controls": True,
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
    parser.add_argument("--env", type=Path, default=quote.base.old.v1.probe.DEFAULT_ENV)
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
