"""Thin one-call adapter for the existing native Luna condition.

The native request, intent, response and receipt are immutable originals. A
separate normalized receipt carries their origin pins. Imports read no secrets.
"""
from copy import deepcopy
from pathlib import Path
from http.client import HTTPResponse, IncompleteRead
import re
import time
from urllib.error import HTTPError
from urllib.request import Request, ProxyHandler, build_opener

from Tools.azure import probe
from Tools.experiments.autoschema_ladder_oct14_v1 import assertion_audit as io
from Tools.experiments.source_anchor_gap_oct20_v1 import native_luna_v2 as native

PROTOCOL = "oneagent-roles-native-luna-wrapper:oct20-v3"


def _pin(path):
    return {"path": str(path.resolve(strict=True)), "sha256": io.sha(path.read_bytes())}


def _save(path, value):
    native.runner.save(path, io.canonical(value))


def read_response_framed(stream):
    """Bounded HTTP body read; sanitized framing facts, never arbitrary headers.

    read(amt) does not itself reject premature Content-Length EOF. Validate the
    declared length and HTTP parser's terminal state independently of JSON syntax.
    """
    limit, raw, error, eof = 262144, b"", None, False
    parser = stream if isinstance(stream, HTTPResponse) else getattr(stream, "fp", None)
    headers = getattr(stream, "headers", None)
    lengths = headers.get_all("Content-Length", []) if headers is not None else []
    encodings = headers.get_all("Transfer-Encoding", []) if headers is not None else []
    declared = None
    valid_length = not lengths
    if len(lengths) == 1 and re.fullmatch(r"[0-9]{1,10}", lengths[0].strip()):
        declared, valid_length = int(lengths[0].strip()), True
    coding = ",".join(encodings).strip().lower()
    mode = "chunked" if coding == "chunked" else "content_length" if lengths else "connection_close_eof"
    headers_valid = valid_length and coding in {"", "chunked"} and not (lengths and encodings)
    try:
        while len(raw) <= limit:
            block = stream.read(min(65536, limit + 1 - len(raw)))
            if type(block) is not bytes:
                raise TypeError("HTTP body must be bytes")
            if not block:
                eof = True
                break
            raw += block
    except IncompleteRead as exc:
        partial = exc.partial if type(exc.partial) is bytes else b""
        raw = (raw + partial)[:limit + 1]
        error = "IncompleteRead"
    except Exception as exc:
        error = type(exc).__name__
    known_parser = isinstance(parser, HTTPResponse)
    remaining = getattr(parser, "length", None) if known_parser else None
    closed = parser.isclosed() if known_parser else False
    chunked = bool(getattr(parser, "chunked", False)) if known_parser else False
    complete = headers_valid and error is None and eof and len(raw) <= limit and known_parser
    if mode == "content_length":
        complete = complete and len(raw) == declared and remaining == 0 and not chunked
    elif mode == "chunked":
        complete = complete and chunked and getattr(parser, "chunk_left", None) is None and closed
    else:
        complete = complete and not chunked and bool(getattr(parser, "will_close", False)) and closed
    evidence = {"protocol": "oneagent-v3-bounded-http-framing:v1", "mode": mode,
        "content_length_header_count": len(lengths), "declared_content_length": declared,
        "transfer_encoding_header_count": len(encodings),
        "transfer_encoding": "chunked" if coding == "chunked" else "absent" if not coding else "unsupported",
        "framing_headers_valid": headers_valid, "parser_type_confirmed": known_parser,
        "parser_remaining_content_length": remaining, "parser_chunked": chunked,
        "parser_closed": closed, "EOF_observed": eof, "bytes_read": len(raw),
        "maximum_body_bytes": limit, "read_error_class": error, "complete": bool(complete)}
    return raw, bool(complete), evidence


def azure_wire(config, payload, *, timeout):
    """Existing request/routing policy with a local corrected body reader."""
    request = Request(config.url, data=native.runner.raw_json(payload), method="POST", headers={
        "api-key": config.key, "Accept": "application/json", "Content-Type": "application/json"})
    opener = build_opener(ProxyHandler({}), probe.NoRedirect())
    try:
        with opener.open(request, timeout=timeout) as response:
            raw, complete, framing = read_response_framed(response)
            return response.status, raw, complete, framing
    except HTTPError as exc:
        raw, complete, framing = read_response_framed(exc)
        return exc.code, raw, complete, framing


def call(config, folder, messages, cap, timeout, *, wire=None):
    """Explicit V3 condition using the existing wire, safety and decoder helpers.

    One attempt only. The completion cap includes internal reasoning. Requested
    low effort and a larger cap do not guarantee acceptance, completion or quality.
    """
    if cap != 32768 or timeout != 300:
        raise ValueError("Frozen V3 completion cap and timeout required")
    folder.mkdir(parents=True, exist_ok=False)
    payload = {**native._payload(messages, cap), "reasoning_effort": "low"}
    request = native.runner.raw_json(payload)
    native.runner.save(folder / "request.json", request)
    _save(folder / "intent.json", {"protocol": PROTOCOL, "request_sha256": io.sha(request),
        "model": "gpt-6-luna", "cap": cap, "reasoning_effort": "low",
        "automatic_retries": 0, "endpoint_sha256": io.sha(config.url.encode())})
    started = time.monotonic()
    receipt = {"model_requested": "gpt-6-luna", "status": "unknown_execution",
        "HTTP_status": None, "HTTP_body_complete": False, "elapsed_seconds": None,
        "provider_usage": None, "requested_reasoning_effort": "low",
        "effective_reasoning_effort": None, "cap_includes_reasoning": True,
        "HTTP_response_received": False, "framing_evidence": None}
    try:
        try:
            response = (wire or azure_wire)(config, payload, timeout=timeout)
            if type(response) not in (tuple, list) or len(response) not in (3, 4):
                raise ValueError("Strict status/body/framing result required")
            status, raw, complete = response[:3]
            framing = response[3] if len(response) == 4 else {"origin": "explicit_test_wire_attestation", "complete": complete}
        except HTTPError as exc:
            raw, complete, framing = read_response_framed(exc)
            status = exc.code
        if type(status) is not int or type(raw) is not bytes or type(complete) is not bool:
            raise ValueError("Strict HTTP result types required")
        receipt.update(HTTP_status=status, HTTP_body_complete=complete,
            response_bytes=len(raw), response_sha256=io.sha(raw),
            HTTP_response_received=True, framing_evidence=framing)
        if complete and status != 200:
            receipt["status"] = "HTTP_rejected"
        native.runner.accounting.safe_object(raw, config, max_bytes=262144,
            strict_json=probe._strict_json)
        native.runner.save(folder / "provider-response.json", raw)
        if not complete or status != 200:
            receipt["status"] = "HTTP_rejected" if complete and status != 200 else "unknown_execution"
            raise RuntimeError("Provider HTTP response was rejected or incomplete")
        text, decoded = native.runner.provider_response(raw, config, cap)
        receipt.update(decoded)
        tokens = decoded["provider_usage"]["completion_tokens"]
        if tokens is not None and tokens > cap:
            receipt["status"] = "output_cap_exceeded"
            raise RuntimeError("Provider completion exceeded the reasoning-inclusive cap")
        if decoded["finish_reason"] != "stop":
            receipt["status"] = "output_incomplete"
            raise RuntimeError("Provider completion did not finish with stop")
        receipt["status"] = "completed"
        return probe._strict_json(text)
    except Exception as error:
        receipt["error_type"] = type(error).__name__
        if receipt["status"] == "completed":
            receipt["status"] = "invalid_json"
        raise
    finally:
        receipt["elapsed_seconds"] = round(time.monotonic() - started, 6)
        _save(folder / "receipt.json", receipt)


class NativeLunaRuntimeV3:
    def __init__(self, output, token_ignored, model, timeout, *, config=None, native_call=None):
        if model != "gpt-6-luna" or timeout != 300:
            raise ValueError("Frozen Luna alias and 300-second timeout required")
        self.output = probe._regular(output).resolve()
        self.config = config if config is not None else probe.load_config()
        if not isinstance(self.config, probe.Config):
            raise ValueError("Existing Foundry Config required")
        self.model, self.timeout = model, timeout
        self.native_call = call if native_call is None else native_call
        self.phase, self.receipts, self.started = None, [], False

    def generate(self, messages, parameters):
        if self.started:
            raise ValueError("Native Luna call is never replayed")
        if parameters != {"max_new_tokens": 32768, "reasoning_effort": "low"}:
            raise ValueError("V3 requires the frozen reasoning-inclusive cap and requested low effort")
        if (type(messages) is not list or not messages or any(type(row) is not dict
                or set(row) != {"role", "content"} or row["role"] not in {"system", "user", "assistant"}
                or type(row["content"]) is not str for row in messages)):
            raise ValueError("Plain-text messages required")
        self.started = True
        folder = self.output / "calls/0000"
        folder.mkdir(parents=True, exist_ok=False)
        # This marker is wrapper entry, NOT evidence of a physical provider POST.
        _save(folder / "native_call_entered.json", {"protocol": PROTOCOL,
            "event": "wrapper_before_native_call", "physical_dispatch_confirmed": False,
            "phase": self.phase, "native_folder": "native/calls/0000"})
        original = self.output / "native/calls/0000"
        row = {"protocol": PROTOCOL, "ordinal": 0, "phase": self.phase,
            "POST_attempts": 0, "physical_dispatch_performed": False,
            "unknown_execution": False, "http_status": None, "HTTP_body_complete": False,
            "provider_completion_confirmed": False, "text_completion_confirmed": False,
            "provider_model": None, "finish_reason": None, "provider_usage": {},
            "requested_output_token_cap": 32768, "cap_includes_reasoning": True,
            "temperature_present": False, "effective_sampling": None,
            "requested_reasoning_effort": "low", "effective_reasoning_effort": None,
            "actual_cost_USD": None, "list_price_estimate_USD": None,
            "HTTP_client_seconds": None, "error_class": None,
            "native_status": None, "native_origin_pins": []}
        self.receipts.append(row)
        try:
            self.native_call(self.config, original, deepcopy(messages), 32768, self.timeout)
            raw = (original / "provider-response.json").read_bytes()
            # Preserve the exact provider content string, including whitespace and
            # field order. native.call's parsed return is intentionally not output.
            text, _ = native.runner.provider_response(raw, self.config, 32768)
            if type(text) is not str:
                raise ValueError("Original complete response must contain text")
            return text
        except Exception as error:
            row["error_class"] = type(error).__name__
            raise
        finally:
            request, intent = original / "request.json", original / "intent.json"
            bound = request.is_file() and intent.is_file()
            if bound:
                claim = io.read(intent)
                if claim.get("request_sha256") != io.sha(request.read_bytes()):
                    raise ValueError("Native request/intent binding differs")
            native_receipt_path = original / "receipt.json"
            receipt = io.read(native_receipt_path) if native_receipt_path.is_file() else {}
            status = receipt.get("status")
            http, complete = receipt.get("HTTP_status"), receipt.get("HTTP_body_complete") is True
            reason = receipt.get("finish_reason")
            terminal = reason in {"stop", "length", "content_filter", "tool_calls", "function_call"}
            confirmed = complete and (http != 200 if type(http) is int else False)
            confirmed = confirmed or (http == 200 and complete and terminal)
            counts = receipt.get("provider_usage")
            response_observed = receipt.get("HTTP_response_received") is True and type(http) is int
            row.update(POST_attempts=int(bound and response_observed),
                physical_dispatch_performed=bool(bound and response_observed) if response_observed else (None if bound else False),
                native_receipt_missing_unknown=bool(bound and not response_observed),
                HTTP_response_received=response_observed, framing_evidence=receipt.get("framing_evidence"),
                unknown_execution=bool(bound and not confirmed), http_status=http,
                HTTP_body_complete=complete, provider_completion_confirmed=bool(http == 200 and complete and terminal),
                text_completion_confirmed=status == "completed" and row["error_class"] is None,
                provider_model=receipt.get("provider_model"), finish_reason=reason,
                provider_usage=deepcopy(counts) if type(counts) is dict else {
                    field: None for field in ("prompt_tokens", "completion_tokens", "total_tokens", "reasoning_tokens", "cached_tokens")},
                metering_complete=receipt.get("metering_complete") is True,
                HTTP_client_seconds=receipt.get("elapsed_seconds"), native_status=status,
                native_origin_pins=[_pin(path) for path in sorted(original.glob("*")) if path.is_file()])
            _save(folder / "receipt.json", row)
