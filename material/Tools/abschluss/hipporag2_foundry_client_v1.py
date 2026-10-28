"""Passive original-OpenAI-client bridge to the existing Azure wire/accounting.

No environment, credential file, client, model or network is touched at import.
The caller supplies config and an explicit wire (CPU tests supply only a fake).
Prompts and native decoding kwargs are the original SDK's, not reimplemented.
SDK retries=0, explicit thinking selection and terminal fail-stop are declared NEW
transport conditions. Native LLMGenerator validation/retry code stays untouched.
Explicit thinking=None leaves all mode controls absent; provider mode is unknown.
"""
from copy import deepcopy
from hashlib import sha256
from math import isfinite
from pathlib import Path
import re
from threading import RLock
import time
from urllib.error import HTTPError

from Tools.azure import probe, accounting, response_diagnostics_v2 as diagnostics
from Tools.azure import http_failure_probe_v2 as transport
from Tools.azure.lamport_source_diagnostic_execution_v2 import private_response_admission
from Tools.experiments.greenfield_kgc_oct14_v1.foundry_runtime import FoundryOnceRuntime, shared
from Tools.wse.strict_native_wse_pipeline_adapter_oct13_v1 import _private_directory
from Experiments.strict_autoschemakg import immutable_publish


PROTOCOL = "hipporag2-original-client-foundry-transport:v1"
ROOT = Path(__file__).resolve().parents[2]
TransportHalt = shared.DispatchHalt  # BaseException: the original retry wrappers cannot swallow it.


def _require(ok, message):
    if not ok:
        raise ValueError(message)


def _save(path, raw):
    _private_directory(Path(path).parent)
    immutable_publish.publish_bytes(path, raw, same=lambda _: False)


class FoundryNotebookClient:
    """Explicit, fresh private call recorder; no added retry or response repair.

    Only this object's injected wire can send. Unknown/private/invalid transport
    results and known non-stop finishes halt the whole object via BaseException.
    Confirmed stopped text, even with missing usage, is returned unmodified to
    the genuine OpenAI SDK. Original format validation can then retry normally,
    producing another physical receipt even for an identical request body.
    """
    _safe_raw = FoundryOnceRuntime._safe_raw

    def __init__(self, output, *, config, wire, model="Kimi-K2.6", timeout=120,
                 thinking="disabled", clock=time.monotonic, max_physical_posts=None,
                 expected_response_model=None):
        _require(isinstance(config, probe.Config) and callable(wire), "Explicit existing config and injected wire required")
        _require(type(model) is str and re.fullmatch(r"[A-Za-z0-9_./:-]{1,200}", model), "Explicit model alias required")
        _require(expected_response_model is None or type(expected_response_model) is str
            and re.fullmatch(r"[A-Za-z0-9_./:-]{1,200}", expected_response_model), "Exact expected response model required")
        _require(type(timeout) in (int, float) and isfinite(timeout) and 0 < timeout <= 600, "Bounded HTTP timeout required")
        _require(thinking is None or type(thinking) is str and thinking == "disabled",
                 "Thinking must explicitly be disabled or absent")
        _require(max_physical_posts is None or type(max_physical_posts) is int and max_physical_posts > 0,
                 "Optional physical POST limit must be a positive strict integer")
        target = probe._regular(output).resolve()
        _require(not any(target.is_relative_to(path.resolve()) for path in
                         (ROOT, ROOT.parent / "Masterarbeit-triple-methods-v1")), "Private evidence must remain outside repositories")
        _require(not target.exists(), "Fresh private output required; existing evidence is never replayed")
        target.mkdir(mode=0o700)
        _private_directory(target)
        self.output, self.config, self.wire = target, config, wire
        self.model, self.timeout, self.thinking, self.clock = model, timeout, thinking, clock
        self.phase, self.receipts, self.halted = None, [], False
        self.max_physical_posts = max_physical_posts
        self.expected_response_model = model if expected_response_model is None else expected_response_model
        self._config_binding, self._lock = (config.url, config.key), RLock()
        _save(target / "condition.json", shared.canonical({"protocol": PROTOCOL,
            "model": model, "endpoint_sha256": sha256(config.url.encode()).hexdigest(),
            "requested_model_alias": model, "expected_response_model": self.expected_response_model,
            "SDK_max_retries": 0, "HTTP_timeout_seconds": timeout, "thinking_requested": thinking,
            "max_physical_posts": max_physical_posts,
            "effective_thinking": None, "native_retry_functions_modified": False,
            "unknown_and_nonstop_fail_stop": True, "POSIX_private_modes_checked": __import__("os").name == "posix",
            "Windows_ACLs_attested": False, "live_execution_approved_by_this_record": False}))
        import httpx
        from openai import OpenAI
        # Genuine SDK object satisfies the unchanged LLMGenerator isinstance
        # contract. No SDK socket path exists: MockTransport delegates only to
        # _send and the explicit injected existing Azure wire beneath it.
        http = httpx.Client(transport=httpx.MockTransport(self._send), timeout=timeout,
                            trust_env=False, follow_redirects=False)
        self.client = OpenAI(api_key='unused',
            base_url="https://hipporag-transport.invalid/v1", http_client=http,
            max_retries=0, timeout=timeout, organization="", project="")

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.client.close()

    def totals(self):
        return accounting.totals(self.receipts)

    def _send(self, request):
        import httpx
        with self._lock:
            if self.halted:
                raise TransportHalt("Previous transport result requires stop; no replay")
            if self.max_physical_posts is not None and sum(row["POST_attempts"] for row in self.receipts) >= self.max_physical_posts:
                self.halted = True
                raise TransportHalt("Caller physical POST limit reached; no new receipt or dispatch")
            row = {"ordinal": len(self.receipts), "phase": self.phase, "POST_attempts": 0,
                "physical_dispatch_performed": False, "unknown_execution": False,
                "http_status": None, "HTTP_body_complete": False, "provider_usage": {},
                "metering_complete": False, "finish_reason": None, "error_class": None,
                "wire_exception_class": None, "raw_body_saved": False,
                "requested_thinking": self.thinking, "effective_thinking": None,
                "requested_model_alias": self.model, "expected_response_model": self.expected_response_model,
                "SDK_max_retries": 0, "native_logical_answer_validity": None}
            self.receipts.append(row)
            folder = self.output / "calls" / f"{row['ordinal']:04d}"
            raw, began = b"", None
            try:
                _require((self.config.url, self.config.key) == self._config_binding, "Explicit provider config changed")
                _require(request.method == "POST" and request.url.path == "/v1/chat/completions", "Only original chat completions supported")
                native = probe._strict_json(request.content)
                _require(type(native) is dict and native.get("model") == self.model, "Native requested model differs")
                messages = native.get("messages")
                _require(type(messages) is list and bool(messages) and all(type(m) is dict
                    and set(m) == {"role", "content"} and m["role"] in {"system", "user", "assistant"}
                    and type(m["content"]) is str for m in messages), "Exact native text messages required")
                cap = native.get("max_tokens")
                _require(type(cap) is int and 0 < cap <= 16384 and native.get("stream", False) is False
                         and native.get("n", 1) == 1, "Unsupported native cap/stream/choice configuration")
                template = native.get("chat_template_kwargs", {})
                _require(type(template) is dict, "Native chat template must be an object")
                if self.thinking is None:
                    _require("thinking" not in native and "reasoning_effort" not in native
                        and "enable_thinking" not in template, "Absent-thinking condition forbids native mode controls")
                    payload = deepcopy(native)
                else:
                    _require("thinking" not in native or native["thinking"] == {"type": "disabled"}, "Native thinking conflicts with declared condition")
                    _require(native.get("reasoning_effort") in (None, "none"), "Native reasoning conflicts with thinking.disabled")
                    _require(template.get("enable_thinking", False) is False,
                             "Native chat template conflicts with thinking.disabled")
                    payload = {**deepcopy(native), "thinking": {"type": "disabled"}}
                encoded = transport.canonical(payload)
                _require(self._safe_raw(request.content) and self._safe_raw(encoded), "Unsafe private request refused")
                row.update(sdk_request_sha256=sha256(request.content).hexdigest(), wire_sha256=sha256(encoded).hexdigest(),
                           requested_output_token_cap=cap)
                _save(folder / "sdk_request.json", request.content)
                _save(folder / "wire_request.json", encoded)
                _save(folder / "dispatch_started.json", shared.canonical({"wire_sha256": row["wire_sha256"],
                    "unsettled_claim_is_unknown": True, "physical_POST_attempts": 1}))
                row.update(POST_attempts=1, physical_dispatch_performed=True, unknown_execution=True)
                began = self.clock()
                try:
                    status, raw, complete = self.wire(self.config, deepcopy(payload), timeout=self.timeout)
                except HTTPError as error:
                    row["wire_exception_class"] = type(error).__name__
                    status, (raw, complete) = error.code, transport._read_response(error)
                _require(type(status) is int and type(raw) is bytes and type(complete) is bool,
                         "Strict existing wire status/body/framing tuple required")
                row.update(http_status=status, HTTP_body_complete=complete)
                accounting.book(row, raw, self.config, cap, max_bytes=diagnostics.MAX_BYTES,
                                strict_json=probe._strict_json, price_estimate=lambda _: None)
                if not complete:
                    row.update(unknown_execution=True, provider_completion_confirmed=False)
                capture = diagnostics.capture_metadata(raw, {self.config.key}, {self.config.url},
                                                       status=status, body_complete=complete)
                _save(folder / "diagnostics.json", shared.canonical(capture))
                admitted = private_response_admission(capture)
                row["private_processing_admitted"] = admitted
                _require(status == 200 and complete and admitted, "Unconfirmed or unsafe provider completion")
                value = accounting.safe_object(raw, self.config, max_bytes=diagnostics.MAX_BYTES, strict_json=probe._strict_json)
                choices = value.get("choices")
                _require(type(choices) is list and len(choices) == 1 and type(choices[0]) is dict,
                         "One native provider choice required")
                choice = choices[0]
                reason = choice.get("finish_reason")
                row["finish_reason"] = reason if reason in diagnostics.FINISH_REASONS else None
                row["model_matches_requested"] = value.get("model") == self.model
                row["model_matches_expected"] = value.get("model") == self.expected_response_model
                row["provider_model"] = value["model"] if type(value.get("model")) is str and re.fullmatch(
                    r"[A-Za-z0-9_./:-]{1,200}", value["model"]) else None
                row["provider_model_sha256"] = sha256(str(value.get("model")).encode()).hexdigest()
                if row["finish_reason"] is not None:
                    row["unknown_execution"] = False
                message = choice.get("message")
                _require(row["model_matches_expected"] and reason == "stop" and type(message) is dict
                    and type(message.get("content")) is str and not message.get("tool_calls"),
                    "Declared transport rejects non-stop/non-text/model-mismatch completion")
                observed = row.get("provider_usage", {}).get("completion_tokens")
                _require(observed is None or observed <= cap, "Reported output exceeds native cap")
                row["text_completion_confirmed"] = True
                return httpx.Response(status, content=raw, headers={"content-type": "application/json"}, request=request)
            except BaseException as error:
                self.halted = True
                row["error_class"] = type(error).__name__
                partial = getattr(error, "raw", getattr(error, "partial", b""))
                if not raw and type(partial) is bytes:
                    raw = partial
                raise TransportHalt("Foundry transport stopped; inspect private receipt, never replay automatically") from None
            finally:
                try:
                    accounting.finish_local(row)
                    row["HTTP_client_seconds"] = max(0, self.clock() - began) if began is not None else 0
                    row.update(response_bytes=len(raw), response_sha256=sha256(raw).hexdigest())
                    if raw and self._safe_raw(raw):
                        path = Path("private_raw/calls") / f"{row['ordinal']:04d}" / "response.raw"
                        _save(self.output / path, raw)
                        row.update(raw_body_saved=True, private_response_body_path=path.as_posix(),
                                   response_archive_complete=row["HTTP_body_complete"])
                    elif raw:
                        row["response_omitted_due_to_publication_guard"] = True
                    _save(folder / "receipt.json", shared.canonical(row))
                except BaseException:
                    self.halted = True
                    raise TransportHalt("Durable private receipt unconfirmed; no replay") from None
