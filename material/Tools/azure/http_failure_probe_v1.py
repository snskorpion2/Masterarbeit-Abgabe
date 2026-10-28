"""One byte-identical retry-as-diagnosis of the already failed HTTP request.

CPU prepare/verify, explicit one-POST execute. This is a new diagnostic, never
a silent retry, resumed thirty-case series, policy bypass or judge admission.

Legacy loss path: quote_controls_v2.execute stops before raw-body publication
on non-200. output_budget_probe.safe_error retains only allowlisted error.code,
not nested errors. A missing saved code therefore proves no particular cause.

Capture policy: bounded strict JSON, actual local credential/endpoint scans,
conservative private-identifier checks before immutable byte publication. Unsafe
or malformed bodies retain their SHA and bounded, redacted structural metadata,
not messages/tracebacks/headers. Diagnostics never alter the prompt or filters.
Official error-shape examples (not proof of this Kimi failure):
https://learn.microsoft.com/en-us/azure/foundry/openai/how-to/use-blocklists
https://learn.microsoft.com/en-us/azure/foundry-classic/foundry-models/concepts/content-filter
"""
from __future__ import annotations

import argparse
from base64 import b64encode
from datetime import datetime
from hashlib import sha256
from pathlib import Path
import re
import time
from urllib.error import HTTPError
from urllib.parse import unquote, urlsplit

from Tools.azure import quote_controls_v2 as controls
from Tools.azure import accounting

HERE = Path(__file__).resolve()
TEST = HERE.parents[1] / "tests/test_azure_http_failure_probe_v1.py"
MAIN = controls.quote.base.old.MAIN_ROOT
PREVIOUS = MAIN / "Experiments/results/abschluss_azure_kimi_quote_controls_oct12_v2"
REQUEST_ID = "claim:84e9005e51dcfa0a3f755b8b0df79b3f15bce84168a32647910732a617229312"
HISTORICAL_PLAN_SHA256 = "d7809e1a40e750bdb9acff48ec7c16d87ca4b4f4a5e8a5862ca6f6ead6ec6c43"
PROTOCOL = "azure-kimi-one-request-failure-capture:v1"
LIMITS = {"max_HTTP_requests": 1, "per_HTTP_timeout_seconds": 120, "max_completion_tokens": 4096,
          "max_response_bytes": 262144, "input_token_reserve_cap": 16384, "automatic_retries": 0,
          "rolling_60s_reserved_tokens_cap": 20000, "minimum_previous_dispatch_gap_seconds": 60.001}
KNOWN_FIELDS = frozenset("error code innererror inner_error details content_filter_result content_filter_results hate sexual violence self_harm jailbreak filtered detected severity message type param target status usage prompt_tokens completion_tokens total_tokens completion_tokens_details reasoning_tokens prompt_tokens_details cached_tokens".split())
canonical, digest, unlinked = controls.canonical, controls.digest, controls.unlinked


def environment_masks(path, config):
    raw = controls.quote.base.old.v1.probe._regular(path).read_bytes()
    if len(raw) > 65536: raise ValueError("Local secret scan boundary invalid")
    secrets, endpoints = {config.key}, {urlsplit(config.url).hostname}
    for line in raw.decode("utf-8-sig").splitlines():
        match = re.match(r"^\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*?)\s*$", line)
        if not match: continue
        value = match[2]
        if value[:1] in ("'", '"'):
            if len(value) < 2 or value[-1] != value[0]: raise ValueError("Ambiguous local secret scan")
            value = value[1:-1]
        else: value = value.split(" #", 1)[0].rstrip()
        if not value: continue
        if re.search(r"key|token|secret|password|passphrase|credential|endpoint|dsn|connection|account|tenant|subscription|email|user", match[1], re.I):
            secrets.add(value)
        if "://" in value:
            secrets.add(value)
            parsed = urlsplit(value)
            host = parsed.hostname
            if host:
                endpoints.add(host)
                if host.endswith((".openai.azure.com", ".services.ai.azure.com")): secrets.add(host.split(".", 1)[0])
            if parsed.path.startswith("/api/projects/"): secrets.add(parsed.path.rsplit("/", 1)[-1])
    return secrets, endpoints


def reflected(text, secrets, endpoints):
    views = (text, unquote(text), unquote(unquote(text)))
    secret = any(s in v or b64encode(s.encode()).decode() in v for s in secrets if s for v in views)
    endpoint = any(h.lower() in v.lower() for h in endpoints if h for v in views)
    return secret, endpoint


def private_pattern(text):
    return bool(re.search(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}|\b[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}\b|/subscriptions/|/resourceGroups/|(?:[\w-]+\.)+(?:openai\.azure\.com|services\.ai\.azure\.com)|(?:api[-_ ]?key|authorization|password|secret|token)\s*[:=]", text, re.I))


def capture_metadata(raw, secrets, endpoints):
    result = {"response_body_sha256": sha256(raw).hexdigest() if isinstance(raw, bytes) else None,
              "response_body_bytes": len(raw) if isinstance(raw, bytes) else None,
              "strict_JSON": False, "raw_body_publishable": False, "publication_guard_reasons": [], "fields": []}
    if not isinstance(raw, bytes) or len(raw) > 262144:
        result["publication_guard_reasons"] = ["body_boundary_invalid"]
        return result
    try:
        value = controls.quote.base.old.v1.probe._strict_json(raw)
        if not isinstance(value, dict): raise ValueError("Object required")
        scan = raw.decode("utf-8") + "\n" + canonical(value).decode()
        secret, endpoint = reflected(scan, secrets, endpoints)
        guards = (["local_secret_reflection"] if secret else []) + (["private_endpoint_reflection"] if endpoint else [])
        if private_pattern(scan): guards.append("private_identifier_or_credential_pattern")
        result.update(strict_JSON=True, publication_guard_reasons=guards, raw_body_publishable=not guards)
        def walk(node, path="$", depth=0):
            if depth > 16 or len(result["fields"]) >= 128: raise ValueError("Metadata boundary invalid")
            if isinstance(node, dict):
                for key, child in node.items():
                    if key not in KNOWN_FIELDS and re.search(r"key|token|secret|password|credential|authorization|endpoint|tenant|subscription|account|email|connection", key, re.I):
                        result["raw_body_publishable"] = False
                        if "sensitive_field_name" not in result["publication_guard_reasons"]: result["publication_guard_reasons"].append("sensitive_field_name")
                    name = key if key in KNOWN_FIELDS else "field_sha256_" + sha256(key.encode()).hexdigest()[:16]
                    walk(child, path + "." + name, depth + 1)
            elif isinstance(node, list):
                for i, child in enumerate(node): walk(child, path + f"[{i}]", depth + 1)
            else:
                item = {"path": path, "type": type(node).__name__}
                if isinstance(node, str):
                    item.update(characters=len(node), value_sha256=sha256(node.encode()).hexdigest())
                    safe = not any(reflected(node, secrets, endpoints)) and not private_pattern(node)
                    if safe and path.endswith(".code") and re.fullmatch(r"[A-Za-z_][A-Za-z0-9_.:-]{0,95}", node): item["value"] = node
                    elif safe and path.endswith(".severity") and node in ("safe", "low", "medium", "high"): item["value"] = node
                elif type(node) is bool or node is None: item["value"] = node
                elif type(node) is int and path.endswith(".status") and 100 <= node <= 599: item["value"] = node
                result["fields"].append(item)
        walk(value)
    except (ValueError, TypeError, UnicodeError, RecursionError):
        result.update(raw_body_publishable=False, publication_guard_reasons=["strict_JSON_or_structure_invalid"], fields=[])
    return result


def read_historical_source():
    """Read a pinned completed run, without approving its old code for execution."""
    common = controls.quote.base.old.v1.common
    frozen = common.strict_plan(unlinked(PREVIOUS / "frozen_plan.json").read_bytes())
    if (frozen.get("plan_sha256") != HISTORICAL_PLAN_SHA256
            or digest({k: v for k, v in frozen.items() if k != "plan_sha256"}) != HISTORICAL_PLAN_SHA256):
        raise ValueError("Pinned historical plan required")
    payloads = common.strict_plan(unlinked(PREVIOUS / "model_inputs/wire_payloads.json").read_bytes())
    if digest(payloads) != frozen["ordered_payloads_sha256"]:
        raise ValueError("Historical ordered request inventory changed")
    return frozen, payloads


def prepare(run_output, env_path=controls.quote.base.old.v1.probe.DEFAULT_ENV):
    frozen = PREVIOUS / "frozen_plan.json"
    original, payloads = read_historical_source()
    summary = controls.quote.base.old.v1.common.strict_plan(unlinked(PREVIOUS / "summary.json").read_bytes())
    receipt = controls.quote.base.old.v1.common.strict_plan(unlinked(PREVIOUS / "HTTP/0018-receipt.json").read_bytes())
    raw = unlinked(PREVIOUS / "HTTP/0018-request.json").read_bytes()
    payload = controls.quote.base.old.v1.common.strict_plan(raw)
    wire_request = canonical(payload)
    task = controls.quote.base.old.v1.common.strict_plan(payload["messages"][-1]["content"].encode())
    if (summary["plan_sha256"] != original["plan_sha256"] or summary["failure"] != "request_rejected"
            or receipt["ordinal"] != 18 or receipt["http_status"] != 400 or receipt["request_id"] != REQUEST_ID
            or task["claim_id"] != REQUEST_ID or payload["max_completion_tokens"] != 4096
            or payload["model"] != "Kimi-K2.6" or raw not in (wire_request, wire_request + b"\n")
            or payload != payloads[18]):
        raise ValueError("Exact original rejected request and terminal evidence required")
    config = controls.quote.base.old.v1.probe.load_config(env_path)
    environment_masks(env_path, config)
    if sha256(config.url.encode()).hexdigest() != original["endpoint_sha256"]: raise ValueError("Original endpoint required")
    upper = len(wire_request) + 256
    worst = (16384 * 0.95 + 4096 * 4) / 1e6
    if upper > 16384 or upper + 4096 >= 20000 or original["budget_reservation"]["pilot_cap_USD"] < 13:
        raise ValueError("Existing pilot/input/minute bounds must hold")
    body = {"protocol": PROTOCOL, "status": "prepared_not_started", "method": "one_exact_failed_request_diagnostic",
        "source_run_plan_sha256": original["plan_sha256"], "request_id": REQUEST_ID,
        "source_evidence_mode": "pinned_historical_run_read_only_not_current_execution_approval",
        "source_reproduction_revision": "cc298b746",
        "accounting_protocol": accounting.PROTOCOL,
        "source_request_path": str(unlinked(PREVIOUS / "HTTP/0018-request.json")),
        "source_request_artifact_byte_sha256": sha256(raw).hexdigest(), "request_byte_sha256": sha256(wire_request).hexdigest(),
        "source_artifact_format_bridge": {"kind": "optional_one_terminal_LF", "original_wire_serialization_preserved": True,
            "source_artifact_bytes_changed": False, "terminal_LF_present": raw.endswith(b"\n")},
        "execution_output": str(Path(run_output).absolute()), "environment_path": str(unlinked(env_path)),
        "endpoint_sha256": original["endpoint_sha256"], "code_root": original["code_root"], "limits": LIMITS,
        "original_source_and_candidate_unchanged": True, "message_or_policy_changes": False,
        "evidence_bindings": [controls.quote.base.old.v1.common.binding(PREVIOUS / n) for n in
            ("frozen_plan.json", "summary.json", "HTTP/0018-request.json", "HTTP/0018-receipt.json", "model_inputs/wire_payloads.json")],
        "historical_code_bindings": original["own_code_and_tests"],
        "own_code_and_tests": [*[controls.quote.base.old.v1.common.binding(Path(b["path"]))
            for b in original["own_code_and_tests"]], *[controls.quote.base.old.v1.common.binding(p)
            for p in (HERE, TEST, accounting.HERE, accounting.TEST)]],
        "resource_v2_path": original["resource_v2_path"], "resource_v2_sha256": original["resource_v2_sha256"],
        "previous_dispatch_UTC": receipt["dispatch_UTC"], "public_list_price": original["public_list_price"],
        "budget_reservation": {"reserved_USD": 2.0, "previous_outstanding_reserved_USD": 11.0,
            "total_conservative_reservation_USD": 13.0, "pilot_cap_USD": 20.0,
            "worst_case_public_list_price_USD": worst, "actual_cost_USD": None, "unknown_costs_are_zero": False},
        "legacy_loss_path": "Non-200 stops before raw save; legacy classifier retains only allowlisted error.code, not inner errors.",
        "raw_capture_policy": "Strict bounded JSON; actual local secrets/endpoints and private identifier patterns checked before immutable bytes; otherwise SHA and redacted structure only.",
        "judge_admitted": False, "quality_measured": False, "hardware_usage": None, "provider_runtime_seconds": None}
    return {**body, "plan_sha256": digest(body)}, wire_request


def write_preparation(prepared, output):
    plan, raw = prepared
    if prepare(plan["execution_output"], plan["environment_path"]) != prepared: raise ValueError("Preparation changed")
    support, _, _ = controls.quote.base.old.v1.common.backend(plan["code_root"])
    target, run = support.transport._fresh(output), support.transport._fresh(plan["execution_output"])
    for a, b in ((target, PREVIOUS), (run, PREVIOUS), (target, run)):
        if a.is_relative_to(b) or b.is_relative_to(a): raise ValueError("Evidence directories must not overlap")
    target.mkdir()
    support._publish(target / "plan.json", plan)
    with (target / "request.json").open("xb") as f: f.write(raw)
    return {"status": "prepared_not_started", "model_calls": 0, "plan_sha256": plan["plan_sha256"]}


def verify(path):
    path = unlinked(path)
    plan = controls.quote.base.old.v1.common.strict_plan(path.read_bytes())
    if plan.get("protocol") != PROTOCOL or plan.get("plan_sha256") != digest({k: v for k, v in plan.items() if k != "plan_sha256"}):
        raise ValueError("Exact sealed diagnostic plan required")
    actual = plan, unlinked(path.parent / "request.json").read_bytes()
    if prepare(plan["execution_output"], plan["environment_path"]) != actual: raise ValueError("Frozen bindings/request changed")
    return actual


def execute(path, *, approved_plan_sha256, wire=controls.quote.base.azure_wire, clock=time.monotonic, epoch=time.time):
    plan, raw_request = verify(path)
    if approved_plan_sha256 != plan["plan_sha256"]: raise ValueError("Exact reviewed plan required")
    previous_epoch = datetime.fromisoformat(plan["previous_dispatch_UTC"].replace("Z", "+00:00")).timestamp()
    if epoch() < previous_epoch + 60.001: raise ValueError("Previous rolling minute must settle before this one diagnostic")
    support, _, Journal = controls.quote.base.old.v1.common.backend(plan["code_root"])
    config = controls.quote.base.old.v1.probe.load_config(plan["environment_path"])
    secrets, endpoints = environment_masks(plan["environment_path"], config)
    target = support.transport._fresh(plan["execution_output"])
    target.mkdir()
    support._publish(target / "frozen_plan.json", plan)
    with (target / "request.json").open("xb") as f: f.write(raw_request)
    start = clock()
    receipt = {"protocol": PROTOCOL, "plan_sha256": plan["plan_sha256"], "request_id": REQUEST_ID,
        "request_byte_sha256": sha256(raw_request).hexdigest(), "POST_attempts": 0, "http_status": None,
        "physical_dispatch_performed": False, "response_archive_complete": False,
        "unknown_execution": True, "metering_complete": False, "response_body_sha256": None,
        "raw_body_saved": False, "actual_cost_USD": None, "list_price_estimate_USD": None,
        "provider_runtime_seconds": None, "hardware_usage": None, "diagnostic_failure": None}
    journal = Journal(target / "ledger")
    with journal.locked():
        key = digest([plan["plan_sha256"], REQUEST_ID])
        journal.record("request_intent", key, request_byte_sha256=receipt["request_byte_sha256"], reserved_USD=2.0)
        try:
            receipt.update(dispatch_UTC=controls.quote.base.old.v1.probe._utc_timestamp())
            journal.record("dispatch", key, **receipt)
            payload = controls.quote.base.old.v1.common.strict_plan(raw_request)
            receipt.update(POST_attempts=1, physical_dispatch_performed=True)
            try: status, raw = wire(config, payload, timeout=120)
            except HTTPError as exc: status, raw = exc.code, exc.read(262145)
            receipt["http_status"] = status if type(status) is int else None
            if isinstance(raw, bytes): receipt["response_body_sha256"] = sha256(raw).hexdigest()
            accounting.book(receipt, raw, config, 4096, max_bytes=262144,
                strict_json=controls.quote.base.old.v1.probe._strict_json,
                price_estimate=controls.quote.base.old.v1.price_estimate)
            latest_config = controls.quote.base.old.v1.probe.load_config(plan["environment_path"])
            latest_secrets, latest_endpoints = environment_masks(plan["environment_path"], latest_config)
            capture = capture_metadata(raw, secrets | latest_secrets, endpoints | latest_endpoints)
            receipt["safe_error_codes"] = [r for r in capture["fields"] if r["path"].endswith(".code") and "value" in r]
            support._publish(target / "response_metadata.json", capture)
            if capture["raw_body_publishable"]:
                with (target / "response-body.json").open("xb") as f: f.write(raw)
                receipt["raw_body_saved"] = True
                receipt["response_archive_complete"] = True
            if status == 200:
                _, details = controls.quote.base.provider_response(raw, config, 4096)
                receipt.update(details)
                if not receipt.get("provider_completion_confirmed"):
                    receipt["diagnostic_failure"] = "provider_completion_unconfirmed"
            else: receipt.update(controls.quote.base.old.safe_error(status, raw))
            verify(path)
            receipt["binding_verification_after"] = True
        except Exception: receipt["diagnostic_failure"] = "transport_capture_or_binding_unknown"
        accounting.finish_local(receipt)
        receipt.update(finish_UTC=controls.quote.base.old.v1.probe._utc_timestamp(), client_elapsed_seconds=max(0.0, clock() - start),
            client_time_is_not_provider_time=True, automatic_retries=0, judge_admitted=False, quality_measured=False)
        journal.record("request_terminal", key, **receipt)
        journal.record("run_terminal", plan["plan_sha256"], receipt_sha256=digest(receipt))
        receipt["ledger_terminal_sha256"] = digest(journal.events()[-1])
        support._publish(target / "receipt.json", receipt)
    return receipt


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group(required=True)
    for mode in ("prepare", "verify", "execute"): modes.add_argument("--" + mode, action="store_true")
    for name in ("run-output", "output", "plan"): parser.add_argument("--" + name, type=Path)
    parser.add_argument("--env", type=Path, default=controls.quote.base.old.v1.probe.DEFAULT_ENV)
    parser.add_argument("--approved-plan-sha256")
    args = parser.parse_args(argv)
    try:
        if args.prepare: result = write_preparation(prepare(args.run_output, args.env), args.output)
        elif args.verify: result = {"verified": True, "model_calls": 0, "plan_sha256": verify(args.plan)[0]["plan_sha256"]}
        else: result = execute(args.plan, approved_plan_sha256=args.approved_plan_sha256)
    except Exception: result = {"protocol": PROTOCOL, "status": "local_guard_failure", "secret_or_error_body_published": False}
    print(canonical(result).decode())
    return int(result.get("status") == "local_guard_failure" or bool(result.get("diagnostic_failure")))


if __name__ == "__main__": raise SystemExit(main())
