"""Separate fresh 4096/8192 output-cap diagnosis. CPU prepare/verify; opt-in execute.

Same three original-order controls, prompts, 280-char reason contract and
backend defaults. No thinking switch, retries, judge admission or F1. Legacy
adapters/evidence are untouched; this version permits 256-KiB response bodies.
"""
from __future__ import annotations

import argparse
from collections import Counter
from copy import deepcopy
from hashlib import sha256
from pathlib import Path
import re
import time
from urllib.error import HTTPError
from Tools.azure import accounting
from urllib.parse import urlsplit
from urllib.request import Request, ProxyHandler, build_opener

from Tools.azure import output_budget_probe as old

HERE = Path(__file__).resolve()
TEST = HERE.parents[1] / "tests/test_azure_output_budget_probe_v2.py"
PREVIOUS_OUTPUT = old.MAIN_ROOT / "Experiments/results/abschluss_azure_kimi_output_budget_oct12_v1"
PROTOCOL = "azure-kimi-paired-output-budget:v2"
LIMITS = {**old.LIMITS, "output_tokens_per_request": [4096, 8192],
          "max_output_tokens_total": 37888, "max_response_bytes": 262144}
canonical, digest, unlinked, FILES = old.canonical, old.digest, old.unlinked, old.FILES


def prepare(source_plan, code_root, run_output, env_path=old.v1.probe.DEFAULT_ENV):
    base, old_pairs, private, human, old_payloads = old.prepare(source_plan, code_root, run_output, env_path)
    pairs, payloads = [], [deepcopy(old_payloads[0])]
    for number, previous in enumerate(old_pairs):
        cap = 4096 if previous["output_cap"] == 1024 else 8192
        pairs.append({**deepcopy(previous), "output_cap": cap})
        payloads.append({**deepcopy(old_payloads[number + 1]), "max_completion_tokens": cap})
    if any(len(canonical(p)) + 256 > 16384 or old.reservation(p) >= 20000 for p in payloads):
        raise ValueError("Input or minute reservation exceeds the same fixed technical limits")
    worst = (7 * 16384 * 0.95 + 37888 * 4.0) / 1e6
    if worst >= 2 or base["budget_reservation"]["pilot_cap_USD"] < 7:
        raise ValueError("Retained five dollars plus new two dollars must fit the existing pilot")
    body = {k: v for k, v in base.items() if k != "plan_sha256"}
    body.update(protocol=PROTOCOL, limits=LIMITS, preparation_adapter_v1_plan_sha256=base["plan_sha256"],
        paired_order="Same selected original case order; cap order alternates 4096/8192 then 8192/4096.",
        public_tasks_sha256=digest(pairs), ordered_payloads_sha256=digest(payloads),
        token_reservations=[old.reservation(p) for p in payloads],
        own_code_and_tests=[*base["own_code_and_tests"], old.v1.common.binding(HERE), old.v1.common.binding(TEST)],
        previous_evidence_bindings=[*base["previous_evidence_bindings"], *[old.v1.common.binding(PREVIOUS_OUTPUT / name)
            for name in ("frozen_plan.json", "summary.json")]],
        budget_reservation={**base["budget_reservation"], "max_output_tokens": 37888,
            "worst_case_public_list_price_USD": worst, "previous_outstanding_reserved_USD": 5.0,
            "previous_output_probe_reserved_USD": 2.0, "total_conservative_reservation_USD": 7.0,
            "previous_known_public_list_price_estimates_USD": [0.0004769, 0.07987842, 0.05847813]})
    return {**body, "plan_sha256": digest(body)}, pairs, private, human, payloads


def write_preparation(prepared, output):
    plan = prepared[0]
    if prepare(plan["source_plan"], plan["code_root"], plan["execution_output"], plan["environment_path"]) != prepared:
        raise ValueError("Preparation changed")
    support, _, _ = old.v1.common.backend(plan["code_root"])
    target, run = support.transport._fresh(output), support.transport._fresh(plan["execution_output"])
    source = unlinked(plan["source_plan"]).parent
    for a, b in ((target, source), (run, source), (target, run)):
        if a.is_relative_to(b) or b.is_relative_to(a): raise ValueError("Evidence directories must not overlap")
    target.mkdir()
    for name, value in zip(("plan.json", *FILES), prepared): support._publish(target / name, value)
    return {"status": "prepared_not_started", "plan_sha256": plan["plan_sha256"], "model_calls": 0}


def verify(plan_path):
    path = unlinked(plan_path)
    plan = old.v1.common.strict_plan(path.read_bytes())
    if plan.get("protocol") != PROTOCOL or plan.get("plan_sha256") != digest({k: v for k, v in plan.items() if k != "plan_sha256"}):
        raise ValueError("Exact sealed V2 diagnostic plan required")
    actual = (plan, *[old.v1.common.strict_plan(unlinked(path.parent / name).read_bytes()) for name in FILES])
    if prepare(plan["source_plan"], plan["code_root"], plan["execution_output"], plan["environment_path"]) != actual:
        raise ValueError("Frozen source/resource/previous evidence/prompt/schema/code or limits changed")
    return actual


def azure_wire(config, payload, *, timeout):
    request = Request(config.url, data=canonical(payload), method="POST", headers={
        "api-key": config.key, "Accept": "application/json", "Content-Type": "application/json"})
    opener = build_opener(ProxyHandler({}), old.v1.probe.NoRedirect())
    with opener.open(request, timeout=timeout) as response:
        return response.status, response.read(LIMITS["max_response_bytes"] + 1)


def provider_response(raw, config, cap):
    """Same primary usage/choice contract, explicitly independent of old 64-KiB caps."""
    if not isinstance(raw, bytes) or len(raw) > 262144:
        raise ValueError("V2 response byte boundary invalid")
    value = accounting.safe_object(raw, config, max_bytes=262144,
                                   strict_json=old.v1.probe._strict_json)
    normalized = canonical(value).decode()
    if config.key in normalized or urlsplit(config.url).hostname in normalized:
        raise ValueError("Credential/private endpoint reflection refused")
    if not isinstance(value, dict): raise ValueError("Provider JSON object required")
    usage = value.get("usage") if isinstance(value.get("usage"), dict) else {}
    integer = lambda v: v if type(v) is int and v >= 0 else None
    counts = {k: integer(usage.get(k)) for k in ("prompt_tokens", "completion_tokens", "total_tokens")}
    for field, container, name in (("reasoning_tokens", "completion_tokens_details", "reasoning_tokens"),
                                   ("cached_tokens", "prompt_tokens_details", "cached_tokens")):
        nested = usage.get(container)
        counts[field] = integer(nested.get(name)) if isinstance(nested, dict) else None
    known = all(counts[k] is not None for k in ("prompt_tokens", "completion_tokens", "total_tokens"))
    meter = known and counts["total_tokens"] == counts["prompt_tokens"] + counts["completion_tokens"]
    meter = meter and (counts["reasoning_tokens"] is None or counts["reasoning_tokens"] <= counts["completion_tokens"])
    meter = meter and (counts["cached_tokens"] is None or counts["cached_tokens"] <= counts["prompt_tokens"])
    choices = value.get("choices")
    if not isinstance(choices, list) or len(choices) != 1 or not isinstance(choices[0], dict):
        raise ValueError("Exactly one provider choice required")
    model = value.get("model")
    if not isinstance(model, str) or not re.fullmatch(r"[A-Za-z0-9_./:-]{1,200}", model): raise ValueError("Model ID required")
    msg = choices[0].get("message")
    text = msg.get("content") if isinstance(msg, dict) else None
    if text is not None and not isinstance(text, str): raise ValueError("Content must be text or null")
    reason = choices[0].get("finish_reason")
    reason = reason if reason in ("stop", "length", "tool_calls", "content_filter", "function_call") else None
    return text, {"provider_usage": counts, "metering_complete": bool(meter), "provider_model": model,
        "finish_reason": reason, "completion_within_requested_cap": known and counts["completion_tokens"] <= cap,
        "reasoning_content_chars": len(msg["reasoning_content"]) if isinstance(msg, dict) and isinstance(msg.get("reasoning_content"), str) else None}


def execute(plan_path, *, approved_plan_sha256, wire=azure_wire, clock=time.monotonic, sleep=time.sleep):
    plan, pairs, private, human, payloads = verify(plan_path)
    if approved_plan_sha256 != plan["plan_sha256"]: raise ValueError("Exact reviewed plan required before HTTP")
    support, _, Journal = old.v1.common.backend(plan["code_root"])
    config = old.v1.probe.load_config(plan["environment_path"])
    target = support.transport._fresh(plan["execution_output"])
    target.mkdir()
    start, history, receipts, observations = clock(), [], [], []
    deadline, failure, smoke, after = start + 900, None, False, False
    labels = {r["request_id"]: r["assessment_only"]["expected_supported"] for r in private["mapping"]}
    for name, value in zip(("frozen_plan.json", *FILES), (plan, pairs, private, human, payloads)): support._publish(target / name, value)
    journal = Journal(target / "ledger")
    with journal.locked():
        journal.record("run_start", plan["plan_sha256"], limits=LIMITS, reserved_USD=2.0, total_retained_reservation_USD=7.0)
        try:
            for ordinal, payload in enumerate(payloads):
                if ordinal >= 7 or not old.v1.wait_for_slot(history, old.reservation(payload), deadline, clock=clock, sleep=sleep):
                    failure = "dispatch_budget_exhausted"
                    break
                pair = pairs[ordinal - 1] if ordinal else None
                task, cap = pair["task"] if pair else None, payload["max_completion_tokens"]
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
                    if remaining <= 0:
                        failure = "dispatch_budget_exhausted"
                        break
                    receipt.update(timeout_seconds=min(120, remaining), dispatch_UTC=old.v1.probe._utc_timestamp())
                    history.append((clock(), old.reservation(payload)))
                    journal.record("dispatch", key, **receipt)
                    receipt.update(POST_attempts=1, physical_dispatch_performed=True)
                    try: status, raw = wire(config, payload, timeout=receipt["timeout_seconds"])
                    except HTTPError as exc: status, raw = exc.code, exc.read(262144 + 1)
                    receipt["http_status"] = status if type(status) is int else None
                    accounting.book(receipt, raw, config, payload["max_completion_tokens"],
                        max_bytes=LIMITS["max_response_bytes"], strict_json=old.v1.probe._strict_json, price_estimate=old.v1.price_estimate)
                    if isinstance(raw, bytes): receipt["response_body_sha256"] = sha256(raw).hexdigest()
                    if type(status) is not int or status != 200:
                        receipt.update(old.safe_error(status, raw))
                        failure = receipt["error_category"]
                        break
                    text, details = provider_response(raw, config, cap)
                    receipt.update(details)
                    with (target / f"HTTP/{ordinal:04d}-success-body.json").open("xb") as stream: stream.write(raw)
                    receipt["response_archive_complete"] = True
                    if not details["metering_complete"] or not details["completion_within_requested_cap"]:
                        failure = "provider_meter_missing_inconsistent_or_cap_exceeded"
                        break
                    if not receipt.get("provider_completion_confirmed"):
                        failure = "provider_completion_unconfirmed"
                        break
                    if details["provider_model"] != old.v1.probe.MODEL:
                        failure = "provider_model_differs"
                        break
                    if details["provider_usage"]["prompt_tokens"] > len(canonical(payload)) + 256:
                        failure = "conservative_input_reservation_exceeded"
                        break
                    cleaned, bridges = old.v1.common.unwrap_format(text)
                    receipt["visible_content_chars"] = len(text) if isinstance(text, str) else None
                    if not task:
                        smoke = details["finish_reason"] == "stop" and old.v1.common.smoke_ready(support.strict_json(cleaned))
                        if not smoke:
                            failure = "source_free_smoke_invalid"
                            break
                    else:
                        parsed = support.parse_response(task, cleaned, execution_confirmed=details["finish_reason"] == "stop")
                        if details["finish_reason"] != "stop": parsed["technical_error"] = "provider_finish_not_stop"
                        parsed.update(axis=task["axis"], output_cap=cap, pair_ordinal=pair["pair_ordinal"], wrapper_bridges=bridges,
                            provider_finish_reason=details["finish_reason"], expected_supported_provisional=labels[identifier],
                            matches_provisional_reference=((parsed["status"] == "supported") == labels[identifier])
                            if parsed["semantic_judgment_available"] else None)
                        observations.append(parsed)
                except Exception:
                    failure = "transport_or_response_unknown"
                    break
                finally:
                    accounting.finish_local(receipt)
                    receipt.update(finish_UTC=old.v1.probe._utc_timestamp(), client_elapsed_seconds=max(0.0, clock() - begin))
                    receipts.append(receipt)
                    support._publish(target / f"HTTP/{ordinal:04d}-receipt.json", receipt)
                    journal.record("request_terminal", key, **receipt)
            verify(plan_path)
            after = True
        except Exception: failure = "post_binding_or_runner_failure"
        summary = {"protocol": PROTOCOL, "plan_sha256": plan["plan_sha256"], "diagnostic_execution_complete":
            failure is None and smoke and after and len(observations) == 6, "failure": failure,
            "HTTP_requests": sum(r["POST_attempts"] for r in receipts), "control_responses": len(observations),
            "unknown_execution_count": sum(r["unknown_execution"] for r in receipts if r["POST_attempts"]),
            "technical_valid_by_cap": {str(cap): sum(o["output_cap"] == cap and o["semantic_judgment_available"]
                for o in observations) for cap in (4096, 8192)}, "technical_error_counts":
                dict(Counter(o.get("technical_error") for o in observations if not o["semantic_judgment_available"])),
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
    parser.add_argument("--env", type=Path, default=old.v1.probe.DEFAULT_ENV)
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
