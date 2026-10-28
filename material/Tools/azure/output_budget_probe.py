"""Explicit isolated 1024/4096 Kimi output-cap diagnostic, never a judge admission.

The first original-order control per EE/EV/VV is selected without labels or
outcome-based filtering. Six fresh paired calls plus one ready smoke. Frozen
v1 adapters and old evidence are read-only. No retries or thinking parameters.
"""
from __future__ import annotations

import argparse
from collections import Counter
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
import time
from urllib.error import HTTPError
from Tools.azure import accounting

from Tools.azure import evaluation_controls as v1
from Tools.abschluss import check_resource_extension as resource_check

HERE = Path(__file__).resolve()
TEST = HERE.parents[1] / "tests/test_azure_output_budget_probe.py"
MAIN_ROOT = HERE.parents[2]
RESOURCE_V2 = MAIN_ROOT / "Tools/abschluss/resource_extension_oct12_v2.json"
PREVIOUS = (MAIN_ROOT / "Experiments/results/abschluss_azure_kimi_smoke_oct12_v1/receipt.json",
            MAIN_ROOT / "Experiments/results/abschluss_azure_kimi_controls_oct12_v1/frozen_plan.json",
            MAIN_ROOT / "Experiments/results/abschluss_azure_kimi_controls_oct12_v1/summary.json")
PROTOCOL = "azure-kimi-paired-output-budget:v1"
LIMITS = {**v1.LIMITS, "max_HTTP_requests": 7, "control_calls": 6,
          "output_tokens_per_request": [1024, 4096], "max_output_tokens_total": 16384,
          "input_token_reserve_cap": 16384}
ERROR_CODES = frozenset(("rate_limit_exceeded", "RateLimitReached", "TooManyRequests", "429",
    "quota_exceeded", "insufficient_quota", "InvalidRequest", "invalid_request_error",
    "Unauthorized", "Forbidden", "DeploymentNotFound", "InternalServerError", "ServiceUnavailable"))
canonical, digest, unlinked = v1.canonical, v1.digest, v1.unlinked
FILES = v1.FILES


def reservation(payload):
    return len(canonical(payload)) + 256 + payload["max_completion_tokens"]


def prepare(source_plan, code_root, run_output, env_path=v1.probe.DEFAULT_ENV):
    extension = v1.common.strict_plan(unlinked(RESOURCE_V2).read_bytes())
    if Path(resource_check.__file__).resolve() != MAIN_ROOT / "Tools/abschluss/check_resource_extension.py":
        raise ValueError("Resource validator must resolve from the declared main repository")
    extension_validation = resource_check.validate(extension, MAIN_ROOT)
    if extension.get("schema_version") != resource_check.VERSION_V2:
        raise ValueError("The actual approved V2 extension is required")
    pilot = extension["resources"]["MicrosoftFoundry"]["initial_pilot_cap_usd"]
    if 5.0 > pilot:
        raise ValueError("Five-dollar conservative total reservation must fit the existing pilot")
    base, tasks, private, human, old_payloads = v1.prepare(source_plan, code_root, run_output, env_path)
    first = {}
    for i, task in enumerate(tasks):
        first.setdefault(task["axis"], i)
    selected = [tasks[i] for i in sorted(first.values())]
    if len(selected) != 3 or set(first) != {"EE", "EV", "VV"}:
        raise ValueError("Exactly three original-order axes required")
    pairs, payloads = [], [deepcopy(old_payloads[0])]
    for pair, i in enumerate(sorted(first.values())):
        for cap in ((1024, 4096) if pair % 2 == 0 else (4096, 1024)):
            pairs.append({"task": deepcopy(tasks[i]), "output_cap": cap, "pair_ordinal": pair})
            payloads.append({**deepcopy(old_payloads[i + 1]), "max_completion_tokens": cap})
    if any(len(canonical(p)) + 256 > 16384 or reservation(p) >= 20000 for p in payloads):
        raise ValueError("Input or rolling-minute reservation exceeds fixed limits")
    worst = (7 * 16384 * 0.95 + 16384 * 4.0) / 1e6
    if worst >= 2:
        raise ValueError("The diagnostic must fit the conservative two-dollar suballocation")
    body = {k: v for k, v in base.items() if k not in ("plan_sha256", "token_reservations", "budget_reservation")}
    body.update(protocol=PROTOCOL, status="prepared_not_started", limits=LIMITS, control_count=6,
        source_control_inventory_count=30, original_order_and_message_texts_preserved=False,
        original_message_texts_preserved=True, source_adapter_plan_sha256=base["plan_sha256"],
        selection_rule="First occurrence per axis in frozen original order; no label or outcome selection.",
        paired_order="Selected original case order; cap order alternates 1024/4096 then 4096/1024.",
        selected_controls=[{"request_id": t["request_id"], "axis": t["axis"]} for t in selected],
        public_tasks_sha256=digest(pairs), ordered_payloads_sha256=digest(payloads),
        token_reservations=[reservation(p) for p in payloads],
        own_code_and_tests=[*base["own_code_and_tests"], v1.common.binding(HERE), v1.common.binding(TEST),
            v1.common.binding(resource_check.__file__)],
        resource_v2_path=str(unlinked(RESOURCE_V2)), resource_v2_sha256=digest(extension),
        resource_v2_validation=extension_validation,
        previous_evidence_bindings=[v1.common.binding(p) for p in PREVIOUS],
        budget_reservation={"kind": "approved_pilot_suballocation_not_account_credit_lock",
            "reserved_USD": 2.0, "worst_case_public_list_price_USD": worst, "max_output_tokens": 16384,
            "max_input_reserve_per_request": 16384, "pilot_cap_USD": pilot,
            "previous_outstanding_reserved_USD": 3.0, "previous_smoke_reserved_USD": 1.0,
            "previous_v1_controls_reserved_USD": 2.0, "total_conservative_reservation_USD": 5.0,
            "previous_known_public_list_price_estimates_USD": [0.0004769, 0.07987842],
            "previous_actual_cost_USD": None, "unknown_costs_are_zero": False,
            "basis": "Explicit root/user pilot allocation: retain all prior reserves until invoiced; not credit balance or actual spending."},
        cached_results_reused=False, fresh_independent_pipeline_repetition=False,
        thinking_parameters_requested=False, hardware_usage=None, model_native_runtime_seconds=None)
    return {**body, "plan_sha256": digest(body)}, pairs, private, human, payloads


def write_preparation(prepared, output):
    plan = prepared[0]
    if prepare(plan["source_plan"], plan["code_root"], plan["execution_output"], plan["environment_path"]) != prepared:
        raise ValueError("Preparation changed before publication")
    support, _, _ = v1.common.backend(plan["code_root"])
    target, run = support.transport._fresh(output), support.transport._fresh(plan["execution_output"])
    original = unlinked(plan["source_plan"]).parent
    for a, b in ((target, original), (run, original), (target, run)):
        if a.is_relative_to(b) or b.is_relative_to(a):
            raise ValueError("Original evidence, preparation and execution must not overlap")
    target.mkdir()
    for name, value in zip(("plan.json", *FILES), prepared):
        support._publish(target / name, value)
    return {"status": "prepared_not_started", "plan_sha256": plan["plan_sha256"], "model_calls": 0}


def verify(plan_path):
    path = unlinked(plan_path)
    plan = v1.common.strict_plan(path.read_bytes())
    if plan.get("protocol") != PROTOCOL or plan.get("plan_sha256") != digest({k: v for k, v in plan.items() if k != "plan_sha256"}):
        raise ValueError("Exact reviewed diagnostic plan required")
    actual = (plan, *[v1.common.strict_plan(unlinked(path.parent / n).read_bytes()) for n in FILES])
    if prepare(plan["source_plan"], plan["code_root"], plan["execution_output"], plan["environment_path"]) != actual:
        raise ValueError("Source, endpoint, controls, prompt, schema, price, limits or code changed")
    return actual


def safe_error(status, raw):
    value = {"http_status": status if type(status) is int else None, "provider_error_code": None,
             "error_category": "unknown_HTTP_failure"}
    if type(status) is int:
        value["error_category"] = ("rate_or_quota_failure" if status == 429 else "authentication_or_authorization_failure"
            if status in (401, 403) else "provider_server_failure" if 500 <= status <= 599
            else "request_rejected" if 400 <= status <= 499 else "redirect_or_non_success_HTTP")
    try:
        if not isinstance(raw, bytes) or len(raw) > LIMITS["max_response_bytes"]:
            return value
        body = v1.probe._strict_json(raw)
        error = body.get("error") if isinstance(body, dict) else None
        code = error.get("code") if isinstance(error, dict) else None
        if isinstance(code, str) and code in ERROR_CODES:
            value["provider_error_code"] = code
    except (ValueError, TypeError, UnicodeError):
        pass
    return value


def execute(plan_path, *, approved_plan_sha256, wire=v1.azure_wire, clock=time.monotonic, sleep=time.sleep):
    plan, pairs, private, human, payloads = verify(plan_path)
    if approved_plan_sha256 != plan["plan_sha256"]:
        raise ValueError("Explicit exact plan approval required before HTTP")
    support, _, Journal = v1.common.backend(plan["code_root"])
    config = v1.probe.load_config(plan["environment_path"])
    target = support.transport._fresh(plan["execution_output"])
    target.mkdir()
    start, history, receipts, observations = clock(), [], [], []
    deadline, failure, smoke, after = start + 900, None, False, False
    labels = {r["request_id"]: r["assessment_only"]["expected_supported"] for r in private["mapping"]}
    for name, value in zip(("frozen_plan.json", *FILES), (plan, pairs, private, human, payloads)):
        support._publish(target / name, value)
    journal = Journal(target / "ledger")
    with journal.locked():
        journal.record("run_start", plan["plan_sha256"], limits=LIMITS, reserved_USD=2.0)
        try:
            for ordinal, payload in enumerate(payloads):
                if ordinal >= 7 or not v1.wait_for_slot(history, reservation(payload), deadline, clock=clock, sleep=sleep):
                    failure = "dispatch_budget_exhausted"
                    break
                pair = pairs[ordinal - 1] if ordinal else None
                task = pair["task"] if pair else None
                request_id = task["request_id"] if task else "source_free_smoke"
                key, begin = digest([plan["plan_sha256"], ordinal, request_id, payload["max_completion_tokens"]]), clock()
                support._publish(target / f"HTTP/{ordinal:04d}-request.json", payload)
                journal.record("request_intent", key, ordinal=ordinal, request_id=request_id, request_sha256=digest(payload))
                receipt = {"ordinal": ordinal, "request_id": request_id, "output_cap": payload["max_completion_tokens"],
                    "POST_attempts": 0, "physical_dispatch_performed": False, "response_archive_complete": False, "unknown_execution": True, "metering_complete": False,
                    "http_status": None, "response_body_sha256": None, "actual_cost_USD": None,
                    "list_price_estimate_USD": None, "provider_runtime_seconds": None, "hardware_usage": None}
                try:
                    remaining = deadline - clock()
                    if remaining <= 0:
                        failure = "dispatch_budget_exhausted"
                        break
                    receipt.update(timeout_seconds=min(120, remaining), dispatch_UTC=v1.probe._utc_timestamp())
                    history.append((clock(), reservation(payload)))
                    journal.record("dispatch", key, **receipt)
                    receipt.update(POST_attempts=1, physical_dispatch_performed=True)
                    try:
                        status, raw = wire(config, payload, timeout=receipt["timeout_seconds"])
                    except HTTPError as exc:
                        status, raw = exc.code, exc.read(LIMITS["max_response_bytes"] + 1)
                    receipt["http_status"] = status if type(status) is int else None
                    accounting.book(receipt, raw, config, payload["max_completion_tokens"],
                        max_bytes=LIMITS["max_response_bytes"], strict_json=v1.probe._strict_json, price_estimate=v1.price_estimate)
                    if isinstance(raw, bytes): receipt["response_body_sha256"] = sha256(raw).hexdigest()
                    if type(status) is not int or status != 200:
                        receipt.update(safe_error(status, raw))
                        failure = receipt["error_category"]
                        break
                    text, details = v1.provider_response(raw, config.key, config.url)
                    details["completion_within_requested_cap"] = (details["provider_usage"]["completion_tokens"] is not None
                        and details["provider_usage"]["completion_tokens"] <= payload["max_completion_tokens"])
                    receipt.update(details)
                    with (target / f"HTTP/{ordinal:04d}-success-body.json").open("xb") as stream: stream.write(raw)
                    receipt["response_archive_complete"] = True
                    if not details["metering_complete"] or not details["completion_within_requested_cap"]:
                        failure = "provider_meter_missing_inconsistent_or_cap_exceeded"
                        break
                    if not receipt.get("provider_completion_confirmed"):
                        failure = "provider_completion_unconfirmed"
                        break
                    if details["provider_model"] != v1.probe.MODEL:
                        failure = "provider_model_differs"
                        break
                    if details["provider_usage"]["prompt_tokens"] > len(canonical(payload)) + 256:
                        failure = "conservative_input_reservation_exceeded"
                        break
                    cleaned, bridges = v1.common.unwrap_format(text)
                    receipt["visible_content_chars"] = len(text) if isinstance(text, str) else None
                    data = v1.probe._strict_json(raw)
                    msg = data["choices"][0]["message"]
                    receipt["reasoning_content_chars"] = len(msg["reasoning_content"]) if isinstance(msg.get("reasoning_content"), str) else None
                    if not task:
                        smoke = details["finish_reason"] == "stop" and v1.common.smoke_ready(support.strict_json(cleaned))
                        if not smoke:
                            failure = "source_free_smoke_invalid"
                            break
                    else:
                        parsed = support.parse_response(task, cleaned, execution_confirmed=details["finish_reason"] == "stop")
                        if details["finish_reason"] != "stop": parsed["technical_error"] = "provider_finish_not_stop"
                        parsed.update(axis=task["axis"], output_cap=pair["output_cap"], pair_ordinal=pair["pair_ordinal"],
                            wrapper_bridges=bridges, provider_finish_reason=details["finish_reason"],
                            expected_supported_provisional=labels[request_id], matches_provisional_reference=
                            ((parsed["status"] == "supported") == labels[request_id]) if parsed["semantic_judgment_available"] else None)
                        observations.append(parsed)
                except Exception:
                    failure = "transport_or_response_unknown"
                    break
                finally:
                    accounting.finish_local(receipt)
                    receipt.update(finish_UTC=v1.probe._utc_timestamp(), client_elapsed_seconds=max(0.0, clock() - begin))
                    receipts.append(receipt)
                    support._publish(target / f"HTTP/{ordinal:04d}-receipt.json", receipt)
                    journal.record("request_terminal", key, **receipt)
            verify(plan_path)
            after = True
        except Exception:
            failure = "post_binding_or_runner_failure"
        complete = failure is None and smoke and after and len(observations) == 6
        summary = {"protocol": PROTOCOL, "plan_sha256": plan["plan_sha256"], "diagnostic_execution_complete": complete,
            "failure": failure, "HTTP_requests": sum(r["POST_attempts"] for r in receipts),
            "unknown_execution_count": sum(r["unknown_execution"] for r in receipts if r["POST_attempts"]),
            "control_responses": len(observations), "technical_valid_by_cap": {str(cap): sum(o["output_cap"] == cap
                and o["semantic_judgment_available"] for o in observations) for cap in (1024, 4096)},
            "technical_error_counts": dict(Counter(o.get("technical_error") for o in observations if not o["semantic_judgment_available"])),
            "actual_cost_USD": None, "provider_runtime_seconds": None, "hardware_usage": None,
            "client_elapsed_seconds": max(0.0, clock() - start), "client_time_is_not_provider_time": True,
            "binding_verification_after": after, "automatic_retries": 0,
            "judge_admitted": False, "human_gold": False, "accuracy": None, "F1": None, "system_MINE_score": None}
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
    parser.add_argument("--env", type=Path, default=v1.probe.DEFAULT_ENV)
    parser.add_argument("--approved-plan-sha256")
    args = parser.parse_args(argv)
    try:
        if args.prepare:
            if any(v is None for v in (args.source_plan, args.code_root, args.run_output, args.output)): raise ValueError("Paths required")
            result = write_preparation(prepare(args.source_plan, args.code_root, args.run_output, args.env), args.output)
        elif args.verify: result = {"verified": True, "model_calls": 0, "plan_sha256": verify(args.plan)[0]["plan_sha256"]}
        else: result = execute(args.plan, approved_plan_sha256=args.approved_plan_sha256)
    except Exception:
        result = {"protocol": PROTOCOL, "status": "local_guard_failure", "secret_or_error_body_published": False}
    print(canonical(result).decode())
    return int(result.get("status") == "local_guard_failure" or bool(result.get("failure")))


if __name__ == "__main__":
    raise SystemExit(main())
