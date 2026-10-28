"""Small, redacted HAWKI access probe for the verified HTWK host only.

The token is loaded from a local env file, never from command-line arguments.
No redirects, retries, cookie sessions, third-party endpoints or local models.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import time
import urllib.error
import urllib.request
from pathlib import Path

HOST = "https://hawki2.htwk-leipzig.de"
ROUTES = {
    "models": "/api/hawki/v1/ai-models",
    "auth": "/api/user",
    "chat-bootstrap": "/chat",
    "validation": "/api/ai-req",
    "smoke": "/api/ai-req",
}
MAX_BYTES = 1_048_576
MODELS = ("gpt-5", "gpt-4.1", "gpt-4.1-nano", "o4-mini", "gemini-2.0-flash")
SMOKE_PROMPT = "Antworte ausschließlich mit OK. Keine Erklärung, keine Werkzeuge, keine Suche."


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def load_token(env_path: Path) -> str:
    values = []
    for line in env_path.read_text(encoding="utf-8-sig").splitlines():
        match = re.match(r"^\s*(?:export\s+)?hawki_api_key\s*=\s*(.*?)\s*$", line, re.I)
        if match:
            value = match.group(1)
            if value[:1] in ("'", '"') and value[-1:] == value[:1]:
                value = value[1:-1]
            elif " #" in value:
                value = value.split(" #", 1)[0].rstrip()
            values.append(value)
    if len(values) != 1 or not values[0] or any(c in values[0] for c in "\r\n"):
        raise ValueError("A single nonempty hawki_api_key entry is required")
    return values[0]


def sanitized(value, token: str):
    if isinstance(value, str):
        return value.replace(token, "[REDACTED]")
    if isinstance(value, list):
        return [sanitized(item, token) for item in value]
    if isinstance(value, dict):
        return {sanitized(str(k), token): sanitized(v, token) for k, v in value.items()}
    return value


def summarize_models(payload):
    rows = payload.get("data", []) if isinstance(payload, dict) else payload
    if not isinstance(rows, list):
        return []
    allowed = {"id", "name", "label", "model", "model_id", "provider", "type", "status", "active", "enabled", "available", "context_length", "max_tokens", "capabilities", "flags"}
    result = []
    for item in rows:
        if not isinstance(item, dict):
            continue
        attrs = item.get("attributes", item)
        if isinstance(attrs, dict):
            row = {k: attrs[k] for k in allowed if k in attrs}
            row["resource_id"] = item.get("id")
            result.append(row)
    return result


def make_smoke_payload(model_id: str):
    if model_id not in MODELS:
        raise ValueError("Model must be one of the user-reported and source-mapped IDs")
    return {"payload": {"model": model_id, "messages": [{"role": "user", "content": {"text": SMOKE_PROMPT}}]}}


def smoke_summary(data):
    content = data.get("content")
    if isinstance(content, dict):
        text = content.get("text")
    elif isinstance(content, str):
        text = content
        try:
            nested = json.loads(content)
            if isinstance(nested, dict):
                text = nested.get("text", text)
        except (ValueError, UnicodeError):
            pass
    else:
        text = None
    result = {"success_reported": data.get("success"), "reply_text": text[:160] if isinstance(text, str) else None, "reply_characters": len(text) if isinstance(text, str) else None, "reply_exact_ok": isinstance(text, str) and text.strip() == "OK", "usage": None}
    usage = data.get("usage")
    if isinstance(usage, dict):
        known_fields = ("prompt_tokens", "completion_tokens", "input_tokens", "output_tokens", "total_tokens", "reasoning_tokens")
        result["usage"] = {key: usage[key] for key in known_fields if isinstance(usage.get(key), (int, float))}
    return result


def request_json(route: str, token: str, payload=None):
    if route not in ROUTES.values():
        raise ValueError("Only researched, explicitly allowlisted routes are permitted")
    req = urllib.request.Request(
        HOST + route,
        data=None if payload is None else json.dumps(payload).encode("utf-8"),
        headers={"Authorization": "Bearer " + token, "Accept": "application/json", "Content-Type": "application/json", "User-Agent": "Masterarbeit-HAWKI-access-probe/1"},
        method="GET" if payload is None else "POST",
    )
    opener = urllib.request.build_opener(NoRedirect())
    started = time.monotonic()
    try:
        response = opener.open(req, timeout=30)
    except urllib.error.HTTPError as exc:
        response = exc
    except Exception as exc:
        return {"route": route, "transport_error_type": type(exc).__name__, "seconds": round(time.monotonic() - started, 3)}
    with response:
        raw = response.read(MAX_BYTES + 1)
        result = {"route": route, "status": response.code, "content_type": response.headers.get("Content-Type"), "body_bytes": len(raw), "body_sha256": hashlib.sha256(raw).hexdigest(), "seconds": round(time.monotonic() - started, 3)}
    if len(raw) > MAX_BYTES:
        result["error"] = "response_size_limit_exceeded"
        return result
    try:
        data = json.loads(raw)
    except (ValueError, UnicodeError):
        result["json"] = False
        return result
    result["json"] = True
    result["top_level_keys"] = sorted(data) if isinstance(data, dict) else []
    if response.code == 200 and route == ROUTES["models"]:
        result["models"] = summarize_models(data)
    elif response.code == 200 and route == ROUTES["smoke"] and isinstance(data, dict):
        result.update(smoke_summary(data))
    elif isinstance(data, dict):
        result["message"] = str(data.get("message", data.get("error", "")))[:300]
        result["error_keys"] = sorted(data.get("errors", {})) if isinstance(data.get("errors"), dict) else []
    return sanitized(result, token)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--env", type=Path, required=True)
    parser.add_argument("--route", choices=ROUTES, default="models")
    parser.add_argument("--model", choices=MODELS)
    args = parser.parse_args()
    token = load_token(args.env)
    # An intentionally missing payload is rejected before any generation.
    if args.route == "smoke" and args.model is None:
        parser.error("--model is required for a single smoke request")
    payload = make_smoke_payload(args.model) if args.route == "smoke" else {} if args.route == "validation" else None
    result = request_json(ROUTES[args.route], token, payload)
    if args.route == "smoke":
        result.update({"model_id": args.model, "prompt": SMOKE_PROMPT, "client_output_token_cap": None, "automatic_retries": 0})
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
