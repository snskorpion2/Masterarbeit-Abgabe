"""Opt-in Kimi diagnostics on the SAME 30 known AI-provisional controls.

CPU-only preparation/verification. One explicit run, 31 POSTs at most, no
retries or semantic repair. Provider and format delivery differ from Ollama.
This is NOT judge admission, human gold, holdout accuracy, F1 or MINE.
"""
from __future__ import annotations

import argparse
from collections import Counter
from hashlib import sha256
import json
from pathlib import Path
import re
import time
from urllib.error import HTTPError
from Tools.azure import accounting
from urllib.parse import urlsplit
from urllib.request import Request, ProxyHandler, build_opener

from Tools.azure import probe
from Tools.hawki import evaluation_controls as common

HERE = Path(__file__).resolve()
TEST = HERE.parents[1] / "tests/test_azure_evaluation_controls.py"
PROTOCOL = "azure-kimi-known-source-controls:v1"
PRICE = {"source": "https://techcommunity.microsoft.com/blog/azure-ai-foundry-blog/introducing-kimi-k2-6-in-microsoft-foundry/4513125",
         "input_USD_per_million": 0.95, "output_USD_per_million": 4.0, "cached_input_USD_per_million": 0.16,
         "kind": "public_list_price_not_account_invoice", "version": "2026-04-20", "deployment_type_user_confirmed": "GlobalStandard"}
LIMITS = {"max_HTTP_requests": 31, "control_calls": 30, "source_free_smoke_calls": 1,
          "output_tokens_per_request": 1024, "dispatch_deadline_seconds": 900,
          "per_HTTP_timeout_seconds": 120, "minimum_start_spacing_seconds": 6,
          "rolling_60s_reserved_tokens_cap": 20000, "max_response_bytes": 65536,
          "automatic_retries": 0, "hard_total_wall_timeout": False}
canonical, digest, unlinked = common.canonical, common.digest, common.unlinked
FILES = ("model_inputs/requests.json", "evaluator_private/assessment.json",
         "HUMAN_REVIEW_PACKET.json", "model_inputs/wire_payloads.json")


def azure_payload(hawki):
    values = hawki["payload"]["messages"]
    return {"model": probe.MODEL, "messages": [{"role": m["role"], "content": m["content"]["text"]} for m in values],
            "max_completion_tokens": 1024, "stream": False, "n": 1}


def token_reservation(payload):
    # Conservative bytes plus a framing reserve, not a native tokenizer count.
    return len(canonical(payload)) + 256 + 1024


def prepare(source_plan, code_root, run_output, env_path=probe.DEFAULT_ENV):
    base, tasks, private, human, old_payloads = common.prepare(source_plan, code_root, run_output)
    config = probe.load_config(env_path)
    payloads = [azure_payload(p) for p in old_payloads]
    if len(payloads) != 31 or any(len(canonical(p)) + 256 > 16384 for p in payloads):
        raise ValueError("Exact bounded 31-request inventory required")
    body = {k: v for k, v in base.items() if k not in ("plan_sha256", "host", "model", "limits")}
    body.update(protocol=PROTOCOL, model=probe.MODEL, limits=dict(LIMITS), host_type=config.host_type,
        route="/openai/v1/chat/completions",
        environment_path=str(unlinked(env_path)), endpoint_sha256=sha256(config.url.encode()).hexdigest(),
        own_code_and_tests=[*base["own_code_and_tests"], *[common.binding(p) for p in
            (HERE, HERE.with_name("probe.py"), TEST, accounting.HERE, accounting.TEST)]],
        accounting_protocol=accounting.PROTOCOL,
        ordered_payloads_sha256=digest(payloads), effective_sampling="backend_default_unknown",
        effective_reasoning="backend_default_unknown", native_schema_requested=False,
        token_reservations=[token_reservation(p) for p in payloads],
        budget_reservation={"kind": "approved_pilot_suballocation_not_account_credit_lock",
            "max_output_tokens": 31744, "input_upper_bound_with_framing": sum(len(canonical(p)) + 256 for p in payloads),
            "max_input_tokens_per_request": 16384, "approved_pilot_USD": 20.0, "this_control_reservation_USD": 2.0,
            "previous_smoke_list_price_estimate_USD": 0.0004769, "worst_case_list_price_estimate_USD": 0.6094848},
        public_list_price=PRICE,
        monetary_budget_verified=False, actual_cost_USD=None, list_price_estimate_USD=None,
        max_completion_tokens_model_acceptance_verified=False,
        claim_guard={**base["claim_guard"], "isolated_model_effect_comparison": False})
    return {**body, "plan_sha256": digest(body)}, tasks, private, human, payloads


def write_preparation(prepared, output):
    plan = prepared[0]
    if prepare(plan["source_plan"], plan["code_root"], plan["execution_output"], plan["environment_path"]) != prepared:
        raise ValueError("Preparation changed")
    support, _, _ = common.backend(plan["code_root"])
    target, run = support.transport._fresh(output), support.transport._fresh(plan["execution_output"])
    original = unlinked(plan["source_plan"]).parent
    for left, right in ((target, original), (run, original), (target, run)):
        if left.is_relative_to(right) or right.is_relative_to(left):
            raise ValueError("Preparation, original evidence and execution must not overlap")
    target.mkdir()
    for name, value in zip(("plan.json", *FILES), prepared):
        support._publish(target / name, value)
    return {"status": "prepared_not_started", "plan_sha256": plan["plan_sha256"], "model_calls": 0}


def verify(plan_path):
    path = unlinked(plan_path)
    plan = common.strict_plan(path.read_bytes())
    if plan.get("protocol") != PROTOCOL or plan.get("plan_sha256") != digest({k: v for k, v in plan.items() if k != "plan_sha256"}):
        raise ValueError("Exact sealed Azure plan required")
    actual = (plan, *[common.strict_plan(unlinked(path.parent / name).read_bytes()) for name in FILES])
    if prepare(plan["source_plan"], plan["code_root"], plan["execution_output"], plan["environment_path"]) != actual:
        raise ValueError("Source, labels, messages, schema, endpoint, code or tests changed")
    return actual


def azure_wire(config, payload, *, timeout):
    request = Request(config.url, data=canonical(payload), method="POST", headers={"api-key": config.key,
        "Accept": "application/json", "Content-Type": "application/json"})
    opener = build_opener(ProxyHandler({}), probe.NoRedirect())
    with opener.open(request, timeout=timeout) as response:
        return response.status, response.read(LIMITS["max_response_bytes"] + 1)


def provider_response(raw, key, endpoint):
    if not isinstance(raw, bytes) or len(raw) > LIMITS["max_response_bytes"]:
        raise ValueError("Response byte boundary invalid")
    text = raw.decode("utf-8")
    value = accounting.safe_object(raw, probe.Config(endpoint, key, "", False),
        max_bytes=LIMITS["max_response_bytes"], strict_json=probe._strict_json)
    normalized = canonical(value).decode()
    if any(secret in text or secret in normalized for secret in (key, urlsplit(endpoint).hostname)):
        raise ValueError("Credential or private endpoint reflection must not be retained")
    meter = probe.response_summary(raw)
    choices = value.get("choices") if isinstance(value, dict) else None
    if not isinstance(choices, list) or len(choices) != 1 or not isinstance(choices[0], dict):
        raise ValueError("Exactly one provider choice required")
    model = value.get("model")
    if not isinstance(model, str) or not re.fullmatch(r"[A-Za-z0-9_./:-]{1,200}", model):
        raise ValueError("Public provider model identifier required")
    message = choices[0].get("message")
    content = message.get("content") if isinstance(message, dict) else None
    if content is not None and not isinstance(content, str):
        raise ValueError("Assistant content must be text or null")
    return content, {"provider_usage": meter["provider_usage"], "metering_complete": meter["metering_complete"],
        "finish_reason": meter["finish_reason"], "provider_model": model,
        "completion_within_requested_cap": meter["provider_usage"]["completion_tokens"] is not None
            and meter["provider_usage"]["completion_tokens"] <= 1024}


def price_estimate(usage):
    if usage["prompt_tokens"] is None or usage["completion_tokens"] is None:
        return None
    cached = usage["cached_tokens"] if usage["cached_tokens"] is not None else 0
    return ((usage["prompt_tokens"] - cached) * 0.95 + cached * 0.16 + usage["completion_tokens"] * 4.0) / 1e6


def wait_for_slot(history, reserve, deadline, *, clock, sleep):
    while True:
        now = clock()
        if now >= deadline:
            return False
        live = [(start, n) for start, n in history if start + 60.001 > now]
        spaced = not history or now - history[-1][0] >= 6
        if spaced and sum(n for _, n in live) + reserve < 20000:
            return True
        sleep(min(6, deadline - now, max(0.001, (history[-1][0] + 6 - now) if not spaced else (live[0][0] + 60.001 - now))))


def execute(plan_path, *, approved_plan_sha256, wire=azure_wire, clock=time.monotonic, sleep=time.sleep):
    plan, tasks, private, human, payloads = verify(plan_path)
    if approved_plan_sha256 != plan["plan_sha256"]:
        raise ValueError("Exact reviewed plan required before any HTTP")
    support, original, Journal = common.backend(plan["code_root"])
    config = probe.load_config(plan["environment_path"])
    target = support.transport._fresh(plan["execution_output"])
    target.mkdir()
    started, history, receipts, observations = clock(), [], [], []
    deadline = started + 900
    failure, smoke, after = None, False, False
    for name, value in zip(("frozen_plan.json", *FILES), (plan, tasks, private, human, payloads)):
        support._publish(target / name, value)
    ledger = Journal(target / "ledger")
    with ledger.locked():
        ledger.record("run_start", plan["plan_sha256"], limits=LIMITS, actual_cost_USD=None)
        try:
            for ordinal, payload in enumerate(payloads):
                if not wait_for_slot(history, token_reservation(payload), deadline, clock=clock, sleep=sleep):
                    failure = "dispatch_budget_exhausted"
                    break
                identifier = "source_free_smoke" if ordinal == 0 else tasks[ordinal - 1]["request_id"]
                key, begin = digest([plan["plan_sha256"], identifier, ordinal]), clock()
                remaining = deadline - begin
                if remaining <= 0 or ordinal >= 31:
                    failure = "dispatch_budget_exhausted"
                    break
                support._publish(target / f"HTTP/{ordinal:04d}-request.json", payload)
                ledger.record("request_intent", key, request_id=identifier, request_sha256=digest(payload))
                receipt = {"request_id": identifier, "ordinal": ordinal, "POST_attempts": 0, "physical_dispatch_performed": False, "response_archive_complete": False,
                    "unknown_execution": True, "metering_complete": False, "dispatch_UTC": probe._utc_timestamp(),
                    "actual_cost_USD": None, "list_price_estimate_USD": None, "provider_runtime_seconds": None,
                    "response_body_sha256": None, "http_status": None}
                try:
                    remaining = deadline - clock()
                    if remaining <= 0:
                        failure = "dispatch_budget_exhausted"
                        break
                    receipt.update(timeout_seconds=min(120, remaining))
                    history.append((clock(), token_reservation(payload)))
                    ledger.record("dispatch", key, **receipt)
                    receipt.update(POST_attempts=1, physical_dispatch_performed=True)
                    status, raw = wire(config, payload, timeout=receipt["timeout_seconds"])
                    receipt["http_status"] = status if type(status) is int else None
                    accounting.book(receipt, raw, config, payload["max_completion_tokens"],
                        max_bytes=LIMITS["max_response_bytes"], strict_json=probe._strict_json, price_estimate=price_estimate)
                    if isinstance(raw, bytes):
                        receipt["response_body_sha256"] = sha256(raw).hexdigest()
                    if type(status) is not int or status != 200:
                        failure = "HTTP_failure_no_error_body_saved"
                        break
                    text, details = provider_response(raw, config.key, config.url)
                    receipt.update(details)
                    # Exact successful JSON bytes, including public usage/model fields.
                    path = target / f"HTTP/{ordinal:04d}-success-body.json"
                    with path.open("xb") as stream:
                        stream.write(raw)
                    receipt["raw_success_JSON_path"] = str(path)
                    receipt["response_archive_complete"] = True
                    if not details["metering_complete"] or not details["completion_within_requested_cap"]:
                        failure = "provider_meter_missing_inconsistent_or_cap_exceeded"
                        break
                    if not receipt.get("provider_completion_confirmed"):
                        failure = "provider_completion_unconfirmed"
                        break
                    if details["provider_model"] != probe.MODEL:
                        failure = "provider_model_differs"
                        break
                    if details["provider_usage"]["prompt_tokens"] > len(canonical(payload)) + 256:
                        failure = "conservative_input_reservation_exceeded"
                        break
                    cleaned, bridges = common.unwrap_format(text)
                    receipt["wrapper_bridges"] = bridges
                    if ordinal == 0:
                        smoke = details["finish_reason"] == "stop" and common.smoke_ready(support.strict_json(cleaned))
                        if not smoke:
                            failure = "source_free_smoke_invalid"
                            break
                    else:
                        parsed = support.parse_response(tasks[ordinal - 1], cleaned,
                            execution_confirmed=details["finish_reason"] == "stop")
                        if details["finish_reason"] != "stop":
                            parsed["technical_error"] = "provider_finish_not_stop"
                        parsed.update(wrapper_bridges=bridges, provider_finish_reason=details["finish_reason"])
                        observations.append(parsed)
                except HTTPError as exc:
                    receipt["http_status"] = exc.code if type(exc.code) is int else None
                    raw = exc.read(LIMITS["max_response_bytes"] + 1)
                    accounting.book(receipt, raw, config, payload["max_completion_tokens"],
                        max_bytes=LIMITS["max_response_bytes"], strict_json=probe._strict_json, price_estimate=price_estimate)
                    failure = "HTTP_failure_no_error_body_saved"
                    break
                except Exception:
                    failure = "transport_or_response_unknown"
                    break
                finally:
                    accounting.finish_local(receipt)
                    receipt.update(finish_UTC=probe._utc_timestamp(), client_elapsed_seconds=max(0.0, clock() - begin))
                    receipts.append(receipt)
                    support._publish(target / f"HTTP/{ordinal:04d}-receipt.json", receipt)
                    ledger.record("request_terminal", key, **receipt)
            verify(plan_path)
            after = True
        except Exception:
            failure = "post_binding_or_runner_failure"
        complete = failure is None and smoke and after and len(observations) == 30
        assessment = original._assessment(tasks, private, observations, technically_complete=complete)
        summary = {"protocol": PROTOCOL, "plan_sha256": plan["plan_sha256"], "review_execution_complete": complete,
            "failure": failure, "control_responses": len(observations), "HTTP_requests": sum(r["POST_attempts"] for r in receipts),
            "technical_valid_controls": sum(r["semantic_judgment_available"] for r in observations),
            "technical_error_counts": dict(Counter(r.get("technical_error") for r in observations if not r["semantic_judgment_available"])),
            "unknown_execution_count": sum(r["unknown_execution"] for r in receipts if r["POST_attempts"]),
            "metering_complete": all(not r["POST_attempts"] or r["metering_complete"] for r in receipts),
            "client_elapsed_seconds": max(0.0, clock() - started), "client_time_is_not_provider_time": True,
            "actual_cost_USD": None,
            "cost_estimate_basis": "Public list prices; unknown cached input conservatively priced as uncached; not an account invoice.",
            "provider_runtime_seconds": None,
            "provider_physical_generation_count": None, "binding_verification_after": after,
            "assessment": assessment, "claim_guard": plan["claim_guard"], "automatic_retries": 0}
        summary.update(accounting.totals(receipts))
        ledger.record("run_terminal", plan["plan_sha256"], summary_sha256=digest(summary))
        summary["ledger_terminal_sha256"] = digest(ledger.events()[-1])
        for name, value in (("responses.json", observations), ("HTTP_receipts.json", receipts), ("summary.json", summary)):
            support._publish(target / name, value)
    return summary


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group(required=True)
    for name in ("prepare", "verify", "execute"):
        modes.add_argument("--" + name, action="store_true")
    for name in ("source-plan", "code-root", "run-output", "output", "plan"):
        parser.add_argument("--" + name, type=Path)
    parser.add_argument("--env", type=Path, default=probe.DEFAULT_ENV)
    parser.add_argument("--approved-plan-sha256")
    args = parser.parse_args(argv)
    try:
        if args.prepare:
            if any(v is None for v in (args.source_plan, args.code_root, args.run_output, args.output)):
                raise ValueError("Preparation paths required")
            result = write_preparation(prepare(args.source_plan, args.code_root, args.run_output, args.env), args.output)
        elif args.verify:
            result = {"verified": True, "model_calls": 0, "plan_sha256": verify(args.plan)[0]["plan_sha256"]}
        else:
            result = execute(args.plan, approved_plan_sha256=args.approved_plan_sha256)
    except Exception:
        result = {"protocol": PROTOCOL, "status": "local_guard_failure", "secret_or_error_body_published": False}
    print(canonical(result).decode())
    return 1 if result.get("status") == "local_guard_failure" or result.get("failure") else 0


if __name__ == "__main__":
    raise SystemExit(main())
