"""Separate strict private processing from unchanged raw publication safety.

V1 and its failed real execution remain unchanged. This transparent version
uses identical payloads, source, transport, accounting, limits and consent.
No raw response or provider field names are ever public. CPU modes never read
credentials, dispatch, allocate funds or admit a judge.
"""
from __future__ import annotations

import argparse
from hashlib import sha256
import importlib.util
import math
from pathlib import Path
import sys
import tempfile
import time
from urllib.error import HTTPError

MAIN = Path(__file__).resolve().parents[2]
OLD = MAIN / "Tools/azure/lamport_source_diagnostic_execution_v1.py"
OLD_SHA = "abdc7ee863cd8120de2a420111b14ca8cefd96f10eb349ec45dd469bfa279ad9"
raw = OLD.read_bytes()
if sha256(raw).hexdigest() != OLD_SHA:
    raise ValueError("Immutable V1 execution changed")
spec = importlib.util.spec_from_file_location("_kimi_ten_execution_original_v1", OLD)
V1 = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = V1
exec(compile(raw, str(OLD), "exec"), V1.__dict__)

HERE = Path(__file__).resolve()
TEST = MAIN / "Tools/tests/test_azure_lamport_source_diagnostic_execution_v2.py"
PROTOCOL = "azure-kimi-neutral-ten-case-execution:oct13-v2"
RESERVATION = "azure-kimi-neutral-ten-case-reservation:oct13-v2"
CONSENT_SHA = V1.CONSENT_SHA
SUPERVISOR, SUPERVISOR_SHA = V1.SUPERVISOR, V1.SUPERVISOR_SHA
WHOLE, DISPATCH, SETTLEMENT, HTTP, CALLS = V1.WHOLE, V1.DISPATCH, V1.SETTLEMENT, V1.HTTP, V1.CALLS
neutral, probe, accounting, diagnostics, transport = V1.neutral, V1.probe, V1.accounting, V1.diagnostics, V1.transport
read, canonical, strict, write = V1.read, V1.canonical, V1.strict, V1.write
require_sha, digest, wait_slot, price_estimate = V1.require_sha, V1.digest, V1.wait_slot, V1.price_estimate


def private_response_admission(capture):
    """No weakened raw policy. Only name-based privacy warnings are nonfatal privately."""
    reasons = capture.get("publication_guard_reasons")
    return (capture.get("strict_JSON") is True and capture.get("HTTP_body_complete") is True
            and type(reasons) is list and all(r == "sensitive_field_name" for r in reasons))


def values(consent_path, consent_sha, output):
    previous, payloads = V1.values(consent_path, consent_sha, output)
    plan = {key: value for key, value in previous.items() if key != "plan_sha256"}
    bindings = {**plan["code_sha256"],
        HERE.relative_to(MAIN).as_posix(): digest(read(HERE)),
        TEST.relative_to(MAIN).as_posix(): digest(read(TEST))}
    plan.update(protocol=PROTOCOL, original_execution_v1_sha256=OLD_SHA,
        code_sha256=bindings, private_processing_publication_separation=True,
        original_privacy_guard_unchanged=True, raw_responses_publicly_published=False,
        private_admission_nonfatal_publication_reason="sensitive_field_name",
        public_summary_is_strict_typed_projection=True,
        original_payload_source_model_transport_accounting_limits_unchanged=True,
        new_execution_requires_fresh_v2_reservation=True)
    return {**plan, "plan_sha256": digest(canonical(plan))}, payloads


def prepare(consent_path, consent_sha, output, run_output):
    target, run = probe._regular(output), probe._regular(run_output)
    if target.exists() or run.exists() or target.is_relative_to(run) or run.is_relative_to(target):
        raise ValueError("Fresh disjoint targets required")
    plan, payloads = values(consent_path, consent_sha, run)
    target.mkdir(parents=True, exist_ok=False)
    write(target / "plan.json", canonical(plan)); write(target / "payloads.json", canonical(payloads))
    return {"plan_sha256": plan["plan_sha256"], "model_calls": 0, "new_reservations": 0, "execution_admitted": False}


def verify(path, expected):
    require_sha(expected)
    path = probe._regular(path)
    plan, payloads = strict(read(path)), strict(read(path.parent / "payloads.json"))
    if (plan.get("plan_sha256") != expected or (plan, payloads) != values(
            plan["consent_path"], plan["new_direct_consent_sha256"], plan["execution_output"])):
        raise ValueError("Exact V2 source/prompt/consent/code/plan binding differs")
    for name, pin in plan["input_sha256"].items():
        read(MAIN / name if not Path(name).is_absolute() else name, pin)
    return plan, payloads


def admit_reservation(path, expected, plan):
    require_sha(expected)
    value = strict(read(path, expected))
    wanted = {"schema": RESERVATION, "state": "reserved", "approved_by_root": True,
        "plan_sha256": plan["plan_sha256"], "consent_sha256": plan["new_direct_consent_sha256"],
        "new_reserved_USD": 1, "retained_historical_reserved_USD": 13, "whole_seconds": 1800,
        "max_POSTs": 11, "budget_pool": "regular", "prior_generation_posts": 0, "budget_reset": False,
        "historical_unknown_costs_released": False, "protected_shared_time_reserve_released": False}
    if any(value.get(k) != v or type(value.get(k)) is not type(v) for k, v in wanted.items()):
        raise ValueError("Fresh separate V2 regular1800s and dollar1 reservation required")
    if probe._regular(value.get("allocation_file", "")) != probe._regular(path) or not value.get("reservation_id"):
        raise ValueError("Original one-shot allocation identity required")
    for before, after, amount in (("remaining_regular_before_seconds", "remaining_regular_after_seconds", 1800),
            ("remaining_authorized_allocation_before_USD", "remaining_authorized_allocation_after_USD", 1)):
        a, b = value.get(before), value.get(after)
        if (any(type(x) not in (int, float) or not math.isfinite(x) for x in (a, b))
                or a < amount or b < 0 or abs(a - amount - b) > 1e-6):
            raise ValueError("No reset or invented zero in time/credit allocation")
    if value["remaining_authorized_allocation_before_USD"] > 187:
        raise ValueError("Historical thirteen-dollar bound cannot disappear")
    prior = value["preceding_accounting"]
    read(prior["path"], require_sha(prior["sha256"]))
    return value


def validate_public_summary(summary):
    """Static field/shape admission. No raw fields, model reasons, names or source text."""
    nulls = ("actual_cost_USD", "provider_runtime_seconds", "quality_score", "system_ranking")
    bools = ("complete_ten_case_review", "judge_admission", "MINE", "list_estimates_are_not_invoice_or_account_debits",
             "metering_complete", "private_processing_publication_separation")
    integers = ("case_responses", "technically_valid_cases", "HTTP_requests", "unknown_executions", "automatic_retries",
                "public_raw_files", "retained_historical_reserved_USD", "private_only_metadata_responses")
    dictionaries = ("known_provider_tokens", "known_provider_token_observations", "provider_token_totals")
    numbers = ("client_elapsed_seconds", "known_list_price_estimate_USD", "list_price_estimate_USD")
    keys = {"protocol", "plan_sha256", "failure", "binding_verification_after", "accounting_protocol",
            *nulls, *bools, *integers, *dictionaries, *numbers}
    if type(summary) is not dict or set(summary) != keys:
        raise ValueError("Public summary allowlist differs")
    if summary["protocol"] != PROTOCOL or summary["accounting_protocol"] != accounting.PROTOCOL:
        raise ValueError("Public fixed protocol differs")
    require_sha(summary["plan_sha256"])
    if any(summary[k] is not None for k in nulls) or any(type(summary[k]) is not bool for k in bools):
        raise ValueError("Unknown cost or typed status differs")
    if summary["binding_verification_after"] is not None and type(summary["binding_verification_after"]) is not bool:
        raise ValueError("Binding status type differs")
    failures = {None, "dispatch_deadline_before_POST", "dispatch_deadline_during_storage_no_POST",
        "dispatch_deadline_after_boundary_no_POST", "response_storage_failure", "HTTP_or_framing_or_private_admission_failed",
        "provider_execution_or_usage_unconfirmed", "model_or_conservative_token_bound_failed", "provider_finish_not_stop",
        "source_free_preflight_invalid", "storage_transport_or_decode_unknown", "post_binding_failed"}
    if summary["failure"] not in failures:
        raise ValueError("Public failure label not fixed")
    for key in integers:
        if type(summary[key]) is not int or summary[key] < 0:
            raise ValueError("Public counter type differs")
    if (summary["HTTP_requests"] > 11 or summary["case_responses"] > 10
            or summary["technically_valid_cases"] > summary["case_responses"]
            or summary["unknown_executions"] > summary["HTTP_requests"]
            or summary["private_only_metadata_responses"] > summary["HTTP_requests"]
            or summary["automatic_retries"] != 0 or summary["public_raw_files"] != 0
            or summary["retained_historical_reserved_USD"] != 13
            or summary["judge_admission"] or summary["MINE"]
            or not summary["private_processing_publication_separation"]):
        raise ValueError("Public counter or admission boundary differs")
    for key in dictionaries:
        value = summary[key]
        if key == "provider_token_totals" and value is None:
            continue
        if (type(value) is not dict or set(value) != set(accounting.TOKEN_FIELDS)
                or any(type(v) is not int or v < 0 for v in value.values())):
            raise ValueError("Public numeric usage projection differs")
    for key in numbers:
        value = summary[key]
        if key == "list_price_estimate_USD" and value is None:
            continue
        if type(value) not in (int, float) or not math.isfinite(value) or value < 0:
            raise ValueError("Public numeric estimate type differs")
    return summary


def run_requests(plan, payloads, packet, source, stage, config, *, started, wire=transport.azure_wire,
                 clock=time.monotonic, sleep=time.sleep, masks=None, binding_check=None):
    """Transparent V1 dispatch copy with only the private/public admission split."""
    receipts, observations, history, failure, smoke = [], [], [], None, False
    secrets, endpoints = masks if masks is not None else ({config.key}, {config.url})
    for ordinal, body in enumerate(payloads):
        if ordinal >= 11 or not wait_slot(history, plan["rolling_token_reservations"][ordinal],
                started + DISPATCH, clock=clock, sleep=sleep):
            failure = "dispatch_deadline_before_POST"; break
        row = {"ordinal": ordinal, "POST_attempts": 0, "physical_dispatch_performed": False,
            "unknown_execution": True, "metering_complete": False, "http_status": None,
            "actual_cost_USD": None, "provider_runtime_seconds": None, "response_archive_complete": False,
            "list_price_estimate_USD": None, "HTTP_body_complete": False}
        begin, label = clock(), f"{ordinal:03d}"
        try:
            raw_request = canonical(body)
            row["request_byte_sha256"] = write(stage / "requests" / (label + ".json"), raw_request)
            write(stage / "intents" / (label + ".json"), canonical(row))
            timeout = min(HTTP, started + SETTLEMENT - clock())
            if clock() - started >= DISPATCH or timeout <= 0:
                failure = "dispatch_deadline_during_storage_no_POST"; break
            write(stage / "boundaries" / (label + ".json"), canonical({
                "possible_dispatch_without_terminal_is_unknown": True, "automatic_refund_or_replay_allowed": False}))
            if clock() - started >= DISPATCH:
                failure = "dispatch_deadline_after_boundary_no_POST"; break
            row.update(POST_attempts=1, physical_dispatch_performed=True)
            history.append((clock(), plan["rolling_token_reservations"][ordinal]))
            try:
                answer = wire(config, body, timeout=min(HTTP, started + SETTLEMENT - clock()))
            except HTTPError as error:
                raw, complete = transport._read_response(error); answer = (error.code, raw, complete)
            if type(answer) not in (tuple, list) or len(answer) != 3:
                raise ValueError("Exact status/raw/framing tuple required")
            status, raw, complete = answer
            if type(raw) is not bytes or type(complete) is not bool:
                raise ValueError("Byte receipt and explicit framing required")
            row.update(http_status=status if type(status) is int else None, HTTP_body_complete=complete)
            row["response_body_sha256"] = digest(raw)
            try:
                write(stage / "responses" / (label + ".raw"), raw)
                row["raw_body_saved_privately"] = True
                row["response_archive_complete"] = complete and len(raw) <= 262144
            except OSError:
                row["raw_body_saved_privately"] = False
            accounting.book(row, raw, config, body["max_completion_tokens"], max_bytes=262144,
                strict_json=strict, price_estimate=price_estimate)
            if not complete:
                row.update(unknown_execution=True, provider_completion_confirmed=False)
            if row["raw_body_saved_privately"] is not True:
                failure = "response_storage_failure"; break
            capture = diagnostics.capture_metadata(raw, secrets, endpoints, status=status, body_complete=complete)
            write(stage / "diagnostics" / (label + ".json"), canonical(capture))
            # Original publication result remains false for sensitive field names.
            row["publication_guard_passed"] = capture["raw_body_publishable"]
            row["private_processing_admitted"] = private_response_admission(capture)
            row["finish_reasons"] = capture["observed_finish_reasons"]
            row["content_filter_finish_reported"] = capture["content_filter_finish_reported"]
            if status != 200 or not complete or len(raw) > 262144 or not row["private_processing_admitted"]:
                failure = "HTTP_or_framing_or_private_admission_failed"; break
            if not row.get("provider_completion_confirmed") or not row.get("metering_complete"):
                failure = "provider_execution_or_usage_unconfirmed"; break
            text, details = neutral.quote.base.provider_response(raw, config, body["max_completion_tokens"])
            if (details["provider_model"] != probe.MODEL or not details["completion_within_requested_cap"]
                    or details["provider_usage"]["prompt_tokens"] > len(raw_request) + 256):
                failure = "model_or_conservative_token_bound_failed"; break
            if details["finish_reason"] != "stop":
                failure = "provider_finish_not_stop"; break
            cleaned, bridge = neutral.quote.base.old.v1.common.unwrap_format(text)
            row["wrapper_bridge"] = bridge
            if ordinal == 0:
                value = strict(cleaned)
                smoke = type(value) is dict and set(value) == {"ok"} and value["ok"] is True
                if not smoke:
                    failure = "source_free_preflight_invalid"; break
            else:
                case = packet["cases"][ordinal - 1]
                try:
                    observation = neutral.parse_judgments(case, source, cleaned)
                except (ValueError, TypeError, KeyError):
                    observation = {"case_id": case["case_id"], "technical_valid": False,
                        "error": "strict_case_or_unique_quote_contract_invalid", "judge_admission": False}
                observations.append(observation)
        except Exception as error:
            row["exception_class"] = type(error).__name__; failure = "storage_transport_or_decode_unknown"; break
        finally:
            accounting.finish_local(row)
            row["client_elapsed_seconds"] = max(0, clock() - begin)
            receipts.append(row); write(stage / "receipts" / (label + ".json"), canonical(row))
    binding_after = None
    if binding_check is not None:
        try:
            binding_check(); binding_after = True
        except Exception:
            binding_after = False; failure = failure or "post_binding_failed"
    summary = {"protocol": PROTOCOL, "plan_sha256": plan["plan_sha256"], "failure": failure,
        "complete_ten_case_review": failure is None and smoke and len(observations) == 10,
        "case_responses": len(observations), "technically_valid_cases": sum(x["technical_valid"] for x in observations),
        "HTTP_requests": sum(x["POST_attempts"] for x in receipts),
        "unknown_executions": sum(x["unknown_execution"] for x in receipts if x["POST_attempts"]),
        "binding_verification_after": binding_after, "actual_cost_USD": None, "provider_runtime_seconds": None,
        "quality_score": None, "system_ranking": None, "judge_admission": False, "MINE": False,
        "automatic_retries": 0, "client_elapsed_seconds": max(0, clock() - started), "public_raw_files": 0,
        "retained_historical_reserved_USD": 13, "list_estimates_are_not_invoice_or_account_debits": True,
        "private_processing_publication_separation": True,
        "private_only_metadata_responses": sum(r.get("private_processing_admitted") is True
            and r.get("publication_guard_passed") is False for r in receipts), **accounting.totals(receipts)}
    validate_public_summary(summary)
    write(stage / "observations.json", canonical(observations)); write(stage / "summary.json", canonical(summary))
    return summary


def worker(path, expected, reservation_path, reservation_sha, env, output, marker_sha, *,
           wire=transport.azure_wire, clock=time.monotonic, sleep=time.sleep):
    output = probe._regular(output)
    start = strict(read(output / "supervisor_start.json"))
    if start.get("protocol") != "own-wse-job-hard-deadline-v2" or start.get("whole_job_seconds") != 1800:
        raise ValueError("Real owned1800s supervisor required before secrets")
    plan, payloads = verify(path, expected); admit_reservation(reservation_path, reservation_sha, plan)
    marker = strict(read(str(reservation_path) + ".consumed.json", marker_sha))
    if (marker.get("plan_sha256") != expected or marker.get("reservation_sha256") != reservation_sha
            or marker.get("output") != str(output) or str(output) != plan["execution_output"]):
        raise ValueError("Consumed allocation and owned supervisor target differ")
    stage = Path(tempfile.mkdtemp(prefix="kimi-ten-case-v2-private-")); stage.chmod(0o700)
    write(output / "private_stage.json", canonical({"path": str(stage), "private_originals_retained": True}))
    packet, source = neutral.neutral_inputs(); config = probe.load_config(env)
    masks = transport.old.environment_masks(env, config)
    summary = run_requests(plan, payloads, packet, source, stage, config,
        started=start["started_monotonic_seconds"], wire=wire, clock=clock, sleep=sleep, masks=masks,
        binding_check=lambda: verify(path, expected))
    write(output / "summary.json", canonical(validate_public_summary(summary)))
    return summary


def execute(path, expected, reservation_path, reservation_sha, env):
    plan, _ = verify(path, expected); admit_reservation(reservation_path, reservation_sha, plan)
    output = probe._regular(plan["execution_output"])
    if output.exists():
        raise ValueError("No resume or replay")
    marker_sha = write(str(reservation_path) + ".consumed.json", canonical({"plan_sha256": expected,
        "reservation_sha256": reservation_sha, "output": str(output), "no_automatic_refund": True}))
    spec = importlib.util.spec_from_file_location("kimi_ten_case_v2_owned_supervisor", SUPERVISOR)
    read(SUPERVISOR, SUPERVISOR_SHA)
    supervisor = importlib.util.module_from_spec(spec); spec.loader.exec_module(supervisor)
    output.mkdir(parents=True, exist_ok=False)
    child = '''import runpy,sys
m=runpy.run_path(sys.argv[1])
try:r=m['worker'](*sys.argv[2:])
except Exception:sys.exit(2)
sys.exit(0 if r['complete_ten_case_review'] else 2)
'''
    result = supervisor.supervise_job(child, [str(HERE), str(Path(path).absolute()), expected,
        str(Path(reservation_path).absolute()), reservation_sha, str(probe._regular(env)), str(output), marker_sha],
        results_root=output, timeout_seconds=1800)
    return {"protocol": PROTOCOL, "supervisor": result, "plan_sha256": expected, "actual_cost_USD": None,
        "automatic_retry": False, "judge_admission": False, "provider_stop_on_client_timeout_attested": False}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    group = p.add_mutually_exclusive_group(required=True)
    for name in ("prepare", "verify", "execute"):
        group.add_argument("--" + name, action="store_true")
    for name in ("consent", "output", "run-output", "plan", "reservation", "env"):
        p.add_argument("--" + name, type=Path)
    for name in ("consent-sha256", "expected-plan-sha256", "reservation-sha256"):
        p.add_argument("--" + name)
    a = p.parse_args()
    try:
        if a.prepare:
            result = prepare(a.consent, a.consent_sha256, a.output, a.run_output)
        elif a.verify:
            result = {"verified": True, "plan_sha256": verify(a.plan, a.expected_plan_sha256)[0]["plan_sha256"], "model_calls": 0}
        else:
            result = execute(a.plan, a.expected_plan_sha256, a.reservation, a.reservation_sha256, a.env)
    except Exception as error:
        print(canonical({"failure": "controlled_guard_failure", "exception_class": type(error).__name__}).decode())
        return 1
    print(canonical(result).decode())
    return int(a.execute and result["supervisor"].get("child_returncode") != 0)


if __name__ == "__main__":
    raise SystemExit(main())
