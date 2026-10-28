"""Explicit one-POST Kimi smoke probe. Prepare is local and never sends requests.

Official contracts checked 2026-10-12:
https://learn.microsoft.com/en-us/azure/foundry/openai/api-version-lifecycle
https://learn.microsoft.com/en-us/rest/api/microsoft-foundry/azureopenai/chat
Only the API cap is documented before dispatch, not its model-specific acceptance.
No account identifiers, credentials, headers, response text or error bodies are
published. Missing prices/runtime/reasoning counts remain unknown, never zero.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass, field
from datetime import datetime, timezone
from hashlib import sha256
import json
import math
from pathlib import Path
import re
import time
from urllib.error import HTTPError
from urllib.parse import urlsplit, urlunsplit
from urllib.request import Request, HTTPRedirectHandler, ProxyHandler, build_opener
from Tools.azure import accounting

MODEL, CAP, TIMEOUT, MAX_BYTES = "Kimi-K2.6", 512, 60, 65536
PROTOCOL = "azure-kimi-single-smoke:v1"
PROMPT = 'Return exactly this JSON object and nothing else: {"ok": true}.'
DEFAULT_ENV = Path(__file__).resolve().parents[2] / ".env"
FIELDS = ("azure_api_key", "project_endpoint", "azure_openai_endpoint")
SUFFIXES = (".openai.azure.com", ".services.ai.azure.com")


@dataclass
class Config:
    url: str = field(repr=False)
    key: str = field(repr=False)
    host_type: str
    project_endpoint_valid: bool


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _regular(path):
    path = Path(path).absolute()
    if any(p.is_symlink() or (hasattr(p, "is_junction") and p.is_junction()) for p in (path, *path.parents)):
        raise ValueError("Linked path refused")
    return path


def _endpoint(value, *, project=False):
    if not isinstance(value, str) or any(c.isspace() for c in value):
        raise ValueError("Endpoint structure invalid")
    parsed = urlsplit(value)
    host = parsed.hostname or ""
    suffix = next((s for s in SUFFIXES if host.endswith(s)), None)
    label = host[:-len(suffix)] if suffix else ""
    if (parsed.scheme != "https" or not suffix or not re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", label)
            or parsed.username or parsed.password or parsed.query or parsed.fragment or parsed.port not in (None, 443)):
        raise ValueError("Only credential-free genuine Azure HTTPS endpoints allowed")
    path = parsed.path.rstrip("/")
    if project:
        if suffix != ".services.ai.azure.com" or not re.fullmatch(r"/api/projects/[A-Za-z0-9_-]+", path):
            raise ValueError("Project endpoint structure invalid")
    elif path not in ("", "/openai/v1"):
        raise ValueError("Only resource root or existing OpenAI v1 base allowed")
    return urlunsplit(("https", host, "/openai/v1/chat/completions", "", "")), suffix[1:]


def load_config(env_path=DEFAULT_ENV):
    raw = _regular(env_path).read_bytes()
    if len(raw) > MAX_BYTES:
        raise ValueError("Environment file too large")
    values = {}
    for line in raw.decode("utf-8-sig").splitlines():
        match = re.match(r"^\s*(?:export\s+)?([a-z_]+)\s*=\s*(.*?)\s*$", line)
        if not match or match[1] not in FIELDS:
            continue
        if match[1] in values:
            raise ValueError("Duplicate Azure field")
        value = match[2]
        if value[:1] in ("'", '"'):
            if len(value) < 2 or value[-1] != value[0]:
                raise ValueError("Malformed quoted Azure field")
            value = value[1:-1]
        elif " #" in value:
            value = value.split(" #", 1)[0].rstrip()
        values[match[1]] = value
    key = values.get("azure_api_key", "")
    if not 16 <= len(key) <= 1024 or any(not 33 <= ord(c) <= 126 for c in key):
        raise ValueError("One printable nonempty Azure key required")
    url, host_type = _endpoint(values.get("azure_openai_endpoint", ""))
    project_valid = False
    if values.get("project_endpoint"):
        _endpoint(values["project_endpoint"], project=True)
        project_valid = True
    return Config(url, key, host_type, project_valid)


def payload():
    return {"model": MODEL, "messages": [{"role": "user", "content": PROMPT}],
            "max_completion_tokens": CAP, "stream": False, "n": 1}


def _prepared(config):
    code_hash = sha256(_regular(__file__).read_bytes()).hexdigest()
    accounting_hash = sha256(_regular(accounting.HERE).read_bytes()).hexdigest()
    binding = sha256(json.dumps({"url": config.url, "payload": payload(), "code_sha256": code_hash,
                               "accounting_code_sha256": accounting_hash},
                               sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    return {"protocol": PROTOCOL, "status": "prepared_not_executed", "deployment": MODEL,
            "selected_endpoint_field": "azure_openai_endpoint", "host_type": config.host_type,
            "route": "/openai/v1/chat/completions", "project_endpoint_valid": config.project_endpoint_valid,
            "api_key_present": True, "request_binding_sha256": binding, "code_sha256": code_hash,
            "accounting_protocol": accounting.PROTOCOL, "accounting_code_sha256": accounting_hash,
            "max_physical_POSTs": 1, "max_completion_tokens": CAP,
            "cap_includes_reasoning_per_API_contract": True, "model_acceptance_verified": False,
            "sampling_changed": False, "tool_or_internet_access_requested": False,
            "redirects": False, "retries": 0, "client_timeout_seconds": TIMEOUT,
            "hard_wall_stop_guaranteed": False, "price_or_credit_balance_queried": False,
            "estimated_cost_USD": None, "provider_runtime_seconds": None,
            "quality_measured": False, "explicit_execution_required": True}


def prepare(env_path=DEFAULT_ENV):
    return _prepared(load_config(env_path))


def _wire(config, body):
    request = Request(config.url, data=body, method="POST", headers={
        "api-key": config.key, "Content-Type": "application/json", "Accept": "application/json"})
    opener = build_opener(ProxyHandler({}), NoRedirect())
    with opener.open(request, timeout=TIMEOUT) as response:
        return response.status, response.read(MAX_BYTES + 1)


def _strict_json(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError("Duplicate JSON field")
            result[key] = value
        return result
    def invalid(_):
        raise ValueError("Nonfinite JSON value")
    return json.loads(raw, object_pairs_hook=pairs, parse_constant=invalid)


def response_summary(raw):
    if not isinstance(raw, bytes) or len(raw) > MAX_BYTES:
        raise ValueError("Response body boundary invalid")
    data = _strict_json(raw.decode("utf-8", errors="strict"))
    if not isinstance(data, dict):
        raise ValueError("Provider JSON object required")
    usage = data.get("usage") if isinstance(data.get("usage"), dict) else {}
    integer = lambda v: v if type(v) is int and v >= 0 else None
    counted = {k: integer(usage.get(k)) for k in ("prompt_tokens", "completion_tokens", "total_tokens")}
    details = usage.get("completion_tokens_details") or {}
    counted["reasoning_tokens"] = integer(details.get("reasoning_tokens")) if isinstance(details, dict) else None
    prompt_details = usage.get("prompt_tokens_details") or {}
    counted["cached_tokens"] = integer(prompt_details.get("cached_tokens")) if isinstance(prompt_details, dict) else None
    known = all(counted[k] is not None for k in ("prompt_tokens", "completion_tokens", "total_tokens"))
    consistent = known and counted["total_tokens"] == counted["prompt_tokens"] + counted["completion_tokens"]
    reasoning_ok = counted["reasoning_tokens"] is None or (known and counted["reasoning_tokens"] <= counted["completion_tokens"])
    cache_ok = counted["cached_tokens"] is None or (known and counted["cached_tokens"] <= counted["prompt_tokens"])
    choices = data.get("choices")
    one = isinstance(choices, list) and len(choices) == 1 and isinstance(choices[0], dict)
    choice = choices[0] if one else {}
    reason = choice.get("finish_reason")
    finish = reason if reason in ("stop", "length", "content_filter", "tool_calls", "function_call") else None
    message = choice.get("message") if isinstance(choice.get("message"), dict) else {}
    sane = False
    try:
        answer = _strict_json(message.get("content"))
        sane = isinstance(answer, dict) and set(answer) == {"ok"} and answer["ok"] is True
    except (ValueError, TypeError, UnicodeError):
        pass
    within_cap = counted["completion_tokens"] <= CAP if known else None
    model_matches = data.get("model") == MODEL
    meter = bool(consistent and reasoning_ok and cache_ok)
    return {"provider_usage": counted, "metering_complete": meter,
            "reported_usage_consistent": bool(consistent), "completion_within_requested_cap": within_cap,
            "finish_reason": finish, "single_choice": one, "response_JSON_sanity": sane,
            "provider_model_matches_requested": model_matches,
            "smoke_passed": bool(one and finish == "stop" and sane and model_matches and meter and within_cap)}


def _publish(path, report):
    with Path(path).open("x", encoding="utf-8") as stream:
        json.dump(report, stream, sort_keys=True, ensure_ascii=False, indent=2)


def _utc_timestamp():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def execute(env_path, output, *, approved_request_sha256, wire=_wire, clock=time.monotonic,
            utc_clock=_utc_timestamp):
    config = load_config(env_path)
    plan = _prepared(config)
    if approved_request_sha256 != plan["request_binding_sha256"]:
        raise ValueError("Exact reviewed request binding required")
    target = _regular(output)
    target.mkdir(parents=True, exist_ok=False)
    _publish(target / "intent.json", plan)
    report = {**plan, "status": "unknown_execution", "POST_attempts": 0,
              "physical_dispatch_performed": False,
              "unknown_execution": True, "metering_complete": False, "http_status": None,
              "actual_cost_USD": None, "provider_runtime_seconds": None, "response_body_sha256": None,
              "model_acceptance_scope": "HTTP acceptance only; no SKU, tariff or physical-generation proof."}
    started = clock()
    report["dispatch_UTC"] = utc_clock()
    try:
        body = json.dumps(payload(), separators=(",", ":")).encode()
        report.update(POST_attempts=1, physical_dispatch_performed=True)
        status, raw = wire(config, body)
        if isinstance(raw, bytes):
            report["response_body_sha256"] = sha256(raw).hexdigest()
        report["http_status"] = status if type(status) is int else None
        accounting.book(report, raw, config, CAP, max_bytes=MAX_BYTES,
                        strict_json=_strict_json, price_estimate=lambda usage: None)
        if type(status) is not int or status != 200:
            report.update(status="HTTP_failure", error_category="non_success_HTTP_response")
        else:
            report.update(response_summary(raw))
            report.update(status="smoke_passed" if report["smoke_passed"] else "technical_invalid",
                          model_acceptance_verified=True)
    except HTTPError as error:
        report.update(status="HTTP_failure", http_status=error.code if type(error.code) is int else None,
                      error_category="HTTP_error_body_not_published")
        try:
            accounting.book(report, error.read(MAX_BYTES + 1), config, CAP, max_bytes=MAX_BYTES,
                            strict_json=_strict_json, price_estimate=lambda usage: None)
        except Exception:
            pass
    except Exception:
        report.update(status="unknown_execution", error_category="transport_or_response_boundary_failure")
    finally:
        accounting.finish_local(report)
        elapsed = clock() - started
        report["finish_UTC"] = utc_clock()
        report["client_elapsed_seconds"] = elapsed if math.isfinite(elapsed) and elapsed >= 0 else None
        report["timing_boundary"] = "Client interval includes request and response validation, not native model runtime."
        _publish(target / "receipt.json", report)
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument("--prepare", action="store_true")
    modes.add_argument("--execute", action="store_true")
    parser.add_argument("--env", type=Path, default=DEFAULT_ENV)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--approved-request-sha256")
    args = parser.parse_args(argv)
    if args.prepare and (args.output or args.approved_request_sha256):
        parser.error("Read-only prepare uses only the environment path")
    if args.execute and not (args.output and args.approved_request_sha256):
        parser.error("Explicit execute requires fresh output and reviewed request binding")
    try:
        report = prepare(args.env) if args.prepare else execute(args.env, args.output,
            approved_request_sha256=args.approved_request_sha256)
    except Exception:
        report = {"protocol": PROTOCOL, "status": "local_guard_failure", "secrets_or_raw_error_published": False}
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["status"] in ("prepared_not_executed", "smoke_passed") else 1


if __name__ == "__main__":
    raise SystemExit(main())
