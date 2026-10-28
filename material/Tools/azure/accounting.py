"""Numeric primary usage, independent of answer validity and body publication.

Only sanitized counters and fixed status values enter receipts. No networking,
credentials, model output, retries or semantic validation is performed here.
"""
from base64 import b64encode
from hashlib import sha256
import json
from pathlib import Path
from urllib.parse import unquote, urlsplit

PROTOCOL = "azure-primary-accounting-before-publication:v1"
HERE = Path(__file__).resolve()
TEST = HERE.parents[1] / "tests/test_azure_accounting.py"
TOKEN_FIELDS = ("prompt_tokens", "completion_tokens", "total_tokens")


def safe_object(raw, config, *, max_bytes, strict_json):
    if not isinstance(raw, bytes) or len(raw) > max_bytes:
        raise ValueError("Response byte boundary invalid")
    value = strict_json(raw)
    if not isinstance(value, dict): raise ValueError("Provider JSON object required")
    text = raw.decode("utf-8") + "\n" + json.dumps(value, ensure_ascii=False)
    views = (text, unquote(text), unquote(unquote(text)))
    host = urlsplit(config.url).hostname
    encoded = b64encode(config.key.encode()).decode()
    if any(config.key in v or encoded in v or (host and host.lower() in v.lower()) for v in views):
        raise ValueError("Credential or private endpoint reflection refused")
    return value


def book(receipt, raw, config, cap, *, max_bytes, strict_json, price_estimate):
    """Retain independently reported fields, even if choices later fail validation."""
    if isinstance(raw, bytes): receipt["response_body_sha256"] = sha256(raw).hexdigest()
    receipt.setdefault("response_archive_complete", False)
    receipt["accounting_protocol"] = PROTOCOL
    try:
        value = safe_object(raw, config, max_bytes=max_bytes, strict_json=strict_json)
    except (ValueError, TypeError, UnicodeError, RecursionError):
        receipt["response_accounting_safe"] = False
        return
    receipt["response_accounting_safe"] = True
    usage = value.get("usage") if isinstance(value.get("usage"), dict) else {}
    integer = lambda v: v if type(v) is int and v >= 0 else None
    counts = {name: integer(usage.get(name)) for name in TOKEN_FIELDS}
    for name, container in (("reasoning_tokens", "completion_tokens_details"),
                            ("cached_tokens", "prompt_tokens_details")):
        details = usage.get(container)
        counts[name] = integer(details.get(name)) if isinstance(details, dict) else None
    known = all(counts[name] is not None for name in TOKEN_FIELDS)
    consistent = known and counts["total_tokens"] == counts["prompt_tokens"] + counts["completion_tokens"]
    meter = (consistent and (counts["reasoning_tokens"] is None or counts["reasoning_tokens"] <= counts["completion_tokens"])
             and (counts["cached_tokens"] is None or counts["cached_tokens"] <= counts["prompt_tokens"]))
    receipt.update(provider_usage=counts, metering_complete=bool(meter),
                   reported_usage_consistent=bool(consistent), list_price_estimate_USD=None)
    if meter:
        try:
            receipt["list_price_estimate_USD"] = price_estimate(counts)
        except (ValueError, TypeError, OverflowError):
            receipt["price_estimate_error"] = "numeric_estimate_unavailable"
    choices = value.get("choices")
    one = isinstance(choices, list) and len(choices) == 1 and isinstance(choices[0], dict)
    reason = choices[0].get("finish_reason") if one else None
    terminal = reason in ("stop", "length", "content_filter", "tool_calls", "function_call")
    confirmed = receipt.get("http_status") == 200 and one and terminal
    within = counts["completion_tokens"] is not None and counts["completion_tokens"] <= cap
    receipt["provider_completion_confirmed"] = bool(confirmed)
    if confirmed and meter and within: receipt["unknown_execution"] = False


def totals(receipts):
    physical = [r for r in receipts if r.get("POST_attempts")]
    fields = {name: [r.get("provider_usage", {}).get(name) for r in physical] for name in TOKEN_FIELDS}
    observed = {name: [v for v in values if type(v) is int and v >= 0] for name, values in fields.items()}
    sums = {name: sum(values) for name, values in observed.items()}
    complete = all(r.get("metering_complete", False) for r in physical)
    estimates = [r.get("list_price_estimate_USD") for r in physical]
    return {"accounting_protocol": PROTOCOL, "known_provider_tokens": sums,
            "known_provider_token_observations": {name: len(values) for name, values in observed.items()},
            "provider_token_totals": sums if complete else None, "metering_complete": complete,
            "known_list_price_estimate_USD": sum(v for v in estimates if v is not None),
            "list_price_estimate_USD": sum(estimates) if all(v is not None for v in estimates) else None}


def finish_local(receipt):
    """A failed intent write/deadline before wire is a proven non-dispatch."""
    if not receipt.get("POST_attempts"):
        receipt.update(unknown_execution=False, physical_dispatch_performed=False)
