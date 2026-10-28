"""Bounded status/filter observations, independent of settlement or judgment.

The V1 capture contract is retained, with additional fail-closed secret-scan
views. Unicode unfolding is only for publication safety, never JSON repair or
interpretation of provider status, usage, finish reasons or filter categories.

Official shape contract, checked 2026-10-12:
https://learn.microsoft.com/en-us/azure/foundry-classic/foundry-models/concepts/content-filter
https://learn.microsoft.com/en-us/rest/api/microsoft-foundry/azureopenai/chat
HTTP 200 can carry finish_reason=content_filter. An error nested in a filter
result is distinct from a successful filter result. Neither establishes cost.
"""
from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
import re

from Tools.azure import http_failure_probe_v1 as old

HERE = Path(__file__).resolve()
PROTOCOL = "azure-bounded-status-filter-diagnostics:v2"
MAX_BYTES = 262144
FINISH_REASONS = frozenset(("stop", "length", "content_filter", "tool_calls", "function_call"))
# Begin only at a slash-run start, avoiding quadratic failed matching.
UNICODE_ESCAPES = re.compile(r"(?<!\\)(?:\\+u[0-9a-fA-F]{4})+")
EMAIL_RIGHT = re.compile(r"[A-Za-z0-9.-]+\.[A-Za-z]{2,}", re.I)
EMAIL_LEFT = re.compile(r"[A-Za-z0-9._%+-]", re.I)
PRIVATE_FIXED = re.compile(r"\b[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}\b|/subscriptions/|/resourceGroups/|(?:api[-_ ]?key|authorization|password|secret|token)\s*[:=]", re.I)
ENDPOINT_SUFFIX = re.compile(r"\.(?:openai\.azure\.com|services\.ai\.azure\.com)", re.I)


def _private_pattern(text):
    """V1 indicators without unanchored long-prefix regex backtracking."""
    for index, char in enumerate(text):
        if char == "@" and index and EMAIL_LEFT.fullmatch(text[index - 1]):
            # Match only once at this domain start. Adjacent '@' boundaries
            # partition domain runs, rather than rescanning every left suffix.
            if EMAIL_RIGHT.match(text, index + 1):
                return True
    if PRIVATE_FIXED.search(text):
        return True
    for match in ENDPOINT_SUFFIX.finditer(text):
        index = match.start()
        if index and (text[index - 1].isalnum() or text[index - 1] in "_-"):
            return True
    return False


def _capture_base(raw, secrets, endpoints):
    """Preserve V1's fields and policy, avoiding its quadratic privacy regex."""
    result = {"response_body_sha256": sha256(raw).hexdigest() if isinstance(raw, bytes) else None,
              "response_body_bytes": len(raw) if isinstance(raw, bytes) else None,
              "strict_JSON": False, "raw_body_publishable": False,
              "publication_guard_reasons": [], "fields": []}
    if not isinstance(raw, bytes) or len(raw) > MAX_BYTES:
        result["publication_guard_reasons"] = ["body_boundary_invalid"]
        return result
    try:
        value = old.controls.quote.base.old.v1.probe._strict_json(raw)
        if not isinstance(value, dict):
            raise ValueError("Object required")
        scan = raw.decode("utf-8") + "\n" + old.canonical(value).decode()
        secret, endpoint = old.reflected(scan, secrets, endpoints)
        guards = (["local_secret_reflection"] if secret else []) + (["private_endpoint_reflection"] if endpoint else [])
        if _private_pattern(scan):
            guards.append("private_identifier_or_credential_pattern")
        result.update(strict_JSON=True, publication_guard_reasons=guards, raw_body_publishable=not guards)
        def walk(node, path="$", depth=0):
            if depth > 16 or len(result["fields"]) >= 128:
                raise ValueError("Metadata boundary invalid")
            if isinstance(node, dict):
                for key, child in node.items():
                    if key not in old.KNOWN_FIELDS and re.search(r"key|token|secret|password|credential|authorization|endpoint|tenant|subscription|account|email|connection", key, re.I):
                        result["raw_body_publishable"] = False
                        if "sensitive_field_name" not in guards:
                            guards.append("sensitive_field_name")
                    name = key if key in old.KNOWN_FIELDS else "field_sha256_" + sha256(key.encode()).hexdigest()[:16]
                    walk(child, path + "." + name, depth + 1)
            elif isinstance(node, list):
                for index, child in enumerate(node):
                    walk(child, path + f"[{index}]", depth + 1)
            else:
                item = {"path": path, "type": type(node).__name__}
                if isinstance(node, str):
                    item.update(characters=len(node), value_sha256=sha256(node.encode()).hexdigest())
                    safe = not any(old.reflected(node, secrets, endpoints)) and not _private_pattern(node)
                    if safe and path.endswith(".code") and re.fullmatch(r"[A-Za-z_][A-Za-z0-9_.:-]{0,95}", node):
                        item["value"] = node
                    elif safe and path.endswith(".severity") and node in ("safe", "low", "medium", "high"):
                        item["value"] = node
                elif type(node) is bool or node is None:
                    item["value"] = node
                elif type(node) is int and path.endswith(".status") and 100 <= node <= 599:
                    item["value"] = node
                result["fields"].append(item)
        walk(value)
    except (ValueError, TypeError, UnicodeError, RecursionError):
        result.update(raw_body_publishable=False, publication_guard_reasons=["strict_JSON_or_structure_invalid"], fields=[])
    return result


def _publication_views(text):
    current = text
    views = [text]
    for _ in range(2):
        def unfold(match):
            escaped = re.sub(r"\\+u", lambda _: "\\u", match.group())
            value = json.loads('"' + escaped + '"')
            return value.encode("utf-8", errors="backslashreplace").decode("utf-8")
        decoded = UNICODE_ESCAPES.sub(unfold, current)
        if decoded == current:
            break
        views.append(decoded)
        current = decoded
    return views, bool(UNICODE_ESCAPES.search(current))


def capture_metadata(raw, secrets, endpoints, *, status=None, body_complete=True):
    """Backward-compatible V1 fields plus fixed, literal provider observations."""
    if body_complete is True:
        result = _capture_base(raw, secrets, endpoints)
    else:
        result = {"response_body_sha256": sha256(raw).hexdigest() if isinstance(raw, bytes) else None,
                  "response_body_bytes": len(raw) if isinstance(raw, bytes) else None,
                  "strict_JSON": False, "raw_body_publishable": False,
                  "publication_guard_reasons": ["HTTP_body_incomplete"], "fields": []}
    result.update(diagnostic_protocol=PROTOCOL,
        HTTP_body_complete=body_complete is True,
        http_status=status if type(status) is int and 100 <= status <= 599 else None,
        observed_finish_reasons=[], content_filter_finish_reported=False,
        filter_error_code_reported=False, input_prompt_filtered_cause_confirmed=False,
        provider_execution_confirmed_by_diagnostics=False,
        semantic_judgment_available=False, tokens_or_costs_inferred=False)
    if (not result["strict_JSON"] or not isinstance(raw, bytes) or len(raw) > MAX_BYTES
            or "strict_JSON_or_structure_invalid" in result["publication_guard_reasons"]):
        return result
    try:
        value = old.controls.quote.base.old.v1.probe._strict_json(raw)
        views, unresolved = _publication_views(raw.decode("utf-8") + "\n" + old.canonical(value).decode())
        reasons = result["publication_guard_reasons"]
        for text in views:
            secret, endpoint = old.reflected(text, secrets, endpoints)
            for flag, label in ((secret, "local_secret_reflection"), (endpoint, "private_endpoint_reflection"),
                                (_private_pattern(text), "private_identifier_or_credential_pattern")):
                if flag and label not in reasons:
                    reasons.append(label)
        if unresolved and "bounded_unicode_scan_unconfirmed" not in reasons:
            reasons.append("bounded_unicode_scan_unconfirmed")
        if reasons:
            result["raw_body_publishable"] = False
        # Only original strict JSON is read here. Publication scan views do not
        # become provider data. No message text, private keys or values escape.
        choices = value.get("choices")
        if isinstance(choices, list) and len(choices) <= 16:
            for choice in choices:
                reason = choice.get("finish_reason") if isinstance(choice, dict) else None
                reason = reason if isinstance(reason, str) and reason in FINISH_REASONS else None
                result["observed_finish_reasons"].append(reason)
        result["content_filter_finish_reported"] = "content_filter" in result["observed_finish_reasons"]
        result["filter_error_code_reported"] = any(
            row.get("value") in ("content_filter", "content_filter_error")
            for row in result["fields"] if row["path"].endswith(".code"))
    except (ValueError, TypeError, UnicodeError, RecursionError):
        result.update(raw_body_publishable=False, observed_finish_reasons=[],
                      content_filter_finish_reported=False, filter_error_code_reported=False)
        if "bounded_diagnostic_structure_unconfirmed" not in result["publication_guard_reasons"]:
            result["publication_guard_reasons"].append("bounded_diagnostic_structure_unconfirmed")
    return result


def safe_error(status, raw, secrets, endpoints, *, body_complete=True):
    """Retain legacy non-200 categories; add filter flags instead of guessing cause."""
    result = old.controls.quote.base.old.safe_error(status, raw if body_complete is True else b"")
    capture = capture_metadata(raw, secrets, endpoints, status=status, body_complete=body_complete)
    code = result.get("provider_error_code")
    if code is not None and (any(old.reflected(code, secrets, endpoints)) or _private_pattern(code)):
        result["provider_error_code"] = None
    result.update(diagnostic_protocol=PROTOCOL,
        content_filter_finish_reported=capture["content_filter_finish_reported"],
        filter_error_code_reported=capture["filter_error_code_reported"],
        observed_finish_reasons=capture["observed_finish_reasons"],
        input_prompt_filtered_cause_confirmed=False)
    if type(status) is int and status == 200:
        result["error_category"] = "filtered_completion_reported" if capture["content_filter_finish_reported"] else "HTTP_success_not_quality_admission"
    return result
