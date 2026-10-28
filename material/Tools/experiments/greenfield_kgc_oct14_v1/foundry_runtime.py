"""Budget-free one-POST Foundry transport; imports never read credentials.

Native arguments and actual wire parameters remain separate. No retry, price
tracking, response repair or effective-sampler assertion is performed here.
Provider bodies go only into the caller's ignored private_raw tree.
"""
from copy import deepcopy
from math import isfinite
from pathlib import Path
import re
import time
from urllib.error import HTTPError
from urllib.parse import urlsplit

from Tools.azure import probe, accounting, http_failure_probe_v2 as transport
from Tools.azure import response_diagnostics_v2 as diagnostics
from Tools.azure.lamport_source_diagnostic_execution_v2 import private_response_admission
from Tools.experiments.autoschema_ladder_oct14_v1 import runner as shared

ROOT = Path(__file__).resolve().parents[3]
MAX_BYTES = diagnostics.MAX_BYTES


class FoundryOnceRuntime:
    def __init__(self, output, token_ignored, model, timeout, *, config=None,
                 env_path=ROOT / ".env", wire=transport.azure_wire,
                 clock=time.monotonic, thinking=None, override_output_cap=None, **unused_native_flags):
        if not isinstance(model, str) or re.fullmatch(r"[A-Za-z0-9_./:-]{1,200}", model) is None:
            raise ValueError("Explicit deployment alias required")
        if type(timeout) not in (int, float) or not isfinite(timeout) or not 0 < timeout <= 600:
            raise ValueError("Finite positive HTTP timeout required")
        if thinking is not None and (type(thinking) is not str or thinking not in {"disabled", "enabled"}):
            raise ValueError("Thinking must be absent, disabled or enabled")
        if override_output_cap is not None and (type(override_output_cap) is not int or not 1 <= override_output_cap <= 16384):
            raise ValueError("Explicit output-cap override must be an integer from 1 to 16384")
        self.output = shared.unlinked(output)
        self.config = config if config is not None else probe.load_config(env_path)
        if not isinstance(self.config, probe.Config):
            raise ValueError("Existing explicit Foundry config required")
        self.model, self.timeout, self.wire, self.clock = model, timeout, wire, clock
        self.thinking = thinking
        self.override_output_cap = override_output_cap
        self.phase, self.receipts, self.seen = None, [], set()
        self.halted = False

    def _safe_raw(self, raw):
        if type(raw) is not bytes or len(raw) > MAX_BYTES:
            return False
        try:
            views, unresolved = diagnostics._publication_views(raw.decode("utf-8"))
            endpoints = {self.config.url, urlsplit(self.config.url).hostname}
            return not unresolved and all(not any(diagnostics.old.reflected(
                view, {self.config.key}, endpoints)) and not diagnostics._private_pattern(view)
                for view in views)
        except (ValueError, TypeError, UnicodeError, RecursionError):
            return False

    def generate(self, messages, parameters):
        if self.halted:
            raise shared.DispatchHalt("Previous dispatch unresolved or rejected; no replay")
        if (not messages or any(type(m) is not dict or set(m) != {"role", "content"}
                or m["role"] not in {"system", "user", "assistant"}
                or type(m["content"]) is not str for m in messages) or type(parameters) is not dict):
            raise ValueError("Exact plain-text messages and native arguments required")
        native_cap = parameters.get("max_new_tokens", 2048)
        if type(native_cap) is not int or not 0 < native_cap <= 16384:
            raise ValueError("Positive explicit native output cap required")
        cap = native_cap if self.override_output_cap is None else self.override_output_cap
        payload = {"model": self.model, "messages": deepcopy(messages),
                   "temperature": 0, "max_tokens": cap, "stream": False}
        if self.thinking is not None:
            payload["thinking"] = {"type": self.thinking}
        request = shared.canonical(payload)
        intent = shared.canonical({"phase": self.phase, "messages": deepcopy(messages),
            "native_generation_kwargs": deepcopy(parameters), "wire_parameters": {
                "temperature": 0, "max_tokens": cap, "stream": False},
            "requested_native_output_token_cap": native_cap,
            "output_cap_override_applied": self.override_output_cap is not None,
            "requested_thinking": self.thinking, "effective_thinking": None,
            "effective_sampling": None, "wire_sha256": shared.sha(request)})
        if not self._safe_raw(request) or not self._safe_raw(intent):
            raise shared.DispatchHalt("Private request reflection refused before dispatch")
        identity = shared.sha(shared.canonical([self.phase, payload, parameters]))
        if identity in self.seen:
            raise shared.DispatchHalt("Duplicate request refused before dispatch")
        self.seen.add(identity)
        folder = self.output / "calls" / f"{len(self.receipts):04d}"
        try:
            folder.mkdir(parents=True, exist_ok=False)
        except Exception:
            self.halted = True
            raise shared.DispatchHalt("Existing or unavailable call evidence is never replayed") from None
        row = {"ordinal": len(self.receipts), "phase": self.phase, "POST_attempts": 0,
            "physical_dispatch_performed": False, "unknown_execution": False,
            "http_status": None, "HTTP_body_complete": False, "HTTP_client_seconds": None,
            "provider_usage": {}, "metering_complete": False, "provider_completion_confirmed": False,
            "raw_body_saved": False, "requested_output_token_cap": cap, "effective_sampling": None,
            "requested_native_output_token_cap": native_cap,
            "output_cap_override_applied": self.override_output_cap is not None,
            "private_raw_body_saved": False, "private_response_body_path": None,
            "private_processing_admitted": False, "raw_body_publication_admitted": False,
            "requested_thinking": self.thinking, "effective_thinking": None,
            "reasoning_content_status": "missing", "reasoning_content_characters": None,
            "reasoning_content_sha256": None,
            "provider_model": None, "finish_reason": None, "error_class": None,
            "provider_runtime_seconds": None, "actual_cost_USD": None, "list_price_estimate_USD": None}
        self.receipts.append(row)
        raw, began = b"", None
        try:
            shared.save(folder / "request.json", request)
            shared.save(folder / "native_intent.json", intent)
            shared.save_json(folder / "dispatch_started.json", {"request_sha256": shared.sha(request),
                "physical_POSTs": 1, "unsettled_claim_is_unknown": True})
            row.update(POST_attempts=1, physical_dispatch_performed=True, unknown_execution=True)
            began = self.clock()
            try:
                response = self.wire(self.config, deepcopy(payload), timeout=self.timeout)
            except HTTPError as error:
                raw, complete = transport._read_response(error)
                response = error.code, raw, complete
            except Exception as error:
                partial = getattr(error, "raw", getattr(error, "partial", b""))
                raw = partial if type(partial) is bytes else b""
                raise
            if type(response) not in (tuple, list) or len(response) != 3:
                raise ValueError("Exact status/raw/framing tuple required")
            status, body, complete = response
            if type(status) is not int or type(body) is not bytes or type(complete) is not bool:
                raise ValueError("Strict transport result required")
            raw = body
            row.update(http_status=status, HTTP_body_complete=complete)
            accounting.book(row, raw, self.config, cap, max_bytes=MAX_BYTES,
                            strict_json=probe._strict_json, price_estimate=lambda usage: None)
            row["provider_completion_confirmed"] = row["provider_completion_confirmed"] and complete
            row["unknown_execution"] = True  # Choice validation decides execution, not publication.
            capture = diagnostics.capture_metadata(raw, {self.config.key}, {self.config.url},
                status=status, body_complete=complete)
            shared.save_json(folder / "diagnostics.json", capture)
            row.update(private_processing_admitted=private_response_admission(capture),
                       raw_body_publication_admitted=capture["raw_body_publishable"])
            if status != 200 or not complete or not row["private_processing_admitted"]:
                raise ValueError("Provider completion or safe response unconfirmed")
            value = accounting.safe_object(raw, self.config, max_bytes=MAX_BYTES, strict_json=probe._strict_json)
            choices = value.get("choices")
            if type(choices) is not list or len(choices) != 1 or type(choices[0]) is not dict:
                raise ValueError("Exactly one provider choice required")
            choice, model = choices[0], value.get("model")
            row["provider_model"] = model if isinstance(model, str) and re.fullmatch(r"[A-Za-z0-9_./:-]{1,200}", model) else None
            message = choice.get("message")
            if type(message) is dict and "reasoning_content" in message:
                reasoning = message["reasoning_content"]
                row["reasoning_content_status"] = "null" if reasoning is None else "invalid_type"
                if type(reasoning) is str:
                    row.update(reasoning_content_status="nonempty" if reasoning else "empty",
                        reasoning_content_characters=len(reasoning), reasoning_content_sha256=shared.sha(reasoning.encode()))
            reason = choice.get("finish_reason")
            row["finish_reason"] = reason if reason in diagnostics.FINISH_REASONS else None
            text = choice.get("message", {}).get("content") if type(choice.get("message")) is dict else None
            if row["finish_reason"] is not None:
                row["unknown_execution"] = False
            if reason != "stop" or type(text) is not str or choice.get("message", {}).get("tool_calls"):
                raise ValueError("Complete stopped text required")
            usage = row.get("provider_usage", {})
            if type(usage.get("completion_tokens")) is int and usage["completion_tokens"] > cap:
                raise ValueError("Reported output exceeds requested cap")
            row["text_completion_confirmed"] = True
            return text
        except Exception as error:
            row["error_class"] = type(error).__name__
            self.halted = True
            raise shared.DispatchHalt("Foundry response rejected; no automatic replay") from None
        finally:
            try:
                accounting.finish_local(row)
                row["HTTP_client_seconds"] = max(0, self.clock() - began) if began is not None else 0
                row.update(response_bytes=len(raw), response_sha256=shared.sha(raw))
                if raw and self._safe_raw(raw):
                    private = Path("private_raw/calls") / f"{row['ordinal']:04d}" / "response.raw"
                    shared.save(shared.unlinked(self.output / private), raw)
                    row.update(raw_body_saved=True, private_raw_body_saved=True,
                        private_response_body_path=private.as_posix(),
                        response_archive_complete=row["HTTP_body_complete"])
                elif raw:
                    row["response_omitted_due_to_publication_guard"] = True
                shared.save_json(folder / "receipt.json", row)
            except Exception:
                self.halted = True
                raise shared.DispatchHalt("Receipt storage unconfirmed; no replay") from None


def runtime_factory(env_path=ROOT / ".env", **injected):
    """Bind the credential file explicitly; load it only at runtime creation."""
    def create(output, token_ignored, model, timeout, **native_flags):
        return FoundryOnceRuntime(output, token_ignored, model, timeout,
            env_path=env_path, **injected, **native_flags)
    return create
