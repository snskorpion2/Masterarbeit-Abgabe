"""Explicit WSE backend condition for the existing strict-native Pipeline path.

No runner, queue, environment lookup, lease acquisition or model call at import.
The original README extractor owns preprocessing, prompts, validators and its
three validation retries. This adapter sends each Pipeline item once, without
grammar, input truncation, output-cap adaptation or an additional retry loop.

This is a new provider condition, not proof that Transformers and vLLM defaults,
special-token handling or model weights are identical. An external owner must
admit the binding, lease, reservation and hard whole-job supervisor beforehand.
All source-bearing requests, responses and native outputs stay in private
staging. Native SSE usage is separate from the original generator's estimates.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict, dataclass
import hashlib
import importlib
import json
import math
import os
from pathlib import Path
import re
import stat
import sys
import threading
import time

ROOT = Path(__file__).resolve().parents[2]
CORE = ROOT.parent / "Masterarbeit-triple-methods-v1"
PROTOCOL = "strict-native-wse-pipeline-condition:oct13-v1"


def libraries():
    """Reuse the existing sibling modules and reject ambiguous import origins."""
    previous = list(sys.path)
    sys.path.insert(0, str(CORE))
    try:
        modules = tuple(importlib.import_module("Experiments.triple_methods_v1." + name)
                        for name in ("strict_native_pipeline", "wse_transport_v2", "wse_transport", "contracts"))
        for value in modules:
            if not Path(value.__file__).resolve().is_relative_to(CORE.resolve()):
                raise ValueError("Strict-native WSE helper origin differs")
        return modules
    finally:
        sys.path[:] = previous


def _bytes(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def _sha(raw):
    return hashlib.sha256(raw).hexdigest()


def private_publication():
    """Existing fsynced, exclusive mkstemp/hardlink writer, no new IO format."""
    module = importlib.import_module("Experiments.strict_autoschemakg.immutable_publish")
    if Path(module.__file__).resolve() != (CORE / "Experiments/strict_autoschemakg/immutable_publish.py").resolve():
        raise ValueError("Private immutable writer origin differs")
    return module


def _private_directory(path):
    """Restrict this owned directory before any source-bearing file creation.

    Windows ACL ownership is not certified by POSIX mode bits. Its caller must
    separately admit the ACL; this adapter reports that platform limit openly.
    """
    path = Path(path)
    path.mkdir(mode=0o700, parents=True, exist_ok=True)
    if path.is_symlink() or getattr(path, "is_junction", lambda: False)():
        raise ValueError("Private directory must not be linked")
    if os.name == "posix":
        descriptor = os.open(path, os.O_RDONLY | os.O_DIRECTORY | getattr(os, "O_NOFOLLOW", 0))
        try:
            before = os.fstat(descriptor)
            if not stat.S_ISDIR(before.st_mode) or before.st_uid != os.geteuid():
                raise ValueError("Private directory must belong to the current effective user")
            os.fchmod(descriptor, 0o700)
            actual, named = os.fstat(descriptor), path.lstat()
            if (stat.S_IMODE(actual.st_mode) != 0o700 or actual.st_uid != os.geteuid()
                    or (actual.st_dev, actual.st_ino) != (named.st_dev, named.st_ino)):
                raise ValueError("Private POSIX directory owner or mode unconfirmed")
        finally:
            os.close(descriptor)


def _write(path, raw):
    """Reuse the existing immutable writer, never accept equal republication.

    mkstemp creates the private 0600 inode before writing, independently of an
    ordinary 022 umask. Its existing fsync/exclusive-hardlink policy is retained.
    The original writer stays byte-unchanged and receives no shared global edit.
    """
    path = Path(path)
    _private_directory(path.parent)
    if path.is_symlink() or getattr(path, "is_junction", lambda: False)():
        raise ValueError("Private target must not be linked")
    private_publication().publish_bytes(path, raw, same=lambda target: False)
    if os.name == "posix":
        actual = path.lstat()
        if not stat.S_ISREG(actual.st_mode) or stat.S_IMODE(actual.st_mode) != 0o600 or actual.st_uid != os.geteuid():
            raise ValueError("Private POSIX file owner or mode unconfirmed")


@dataclass(frozen=True)
class WSEPipelineCondition:
    role: str
    model: str
    binding_key: str
    max_generation_calls: int
    max_completion_tokens: int
    deadline_monotonic: float
    execution_kind: str

    def validate(self, clock):
        if (not isinstance(self.role, str) or not self.role or not isinstance(self.model, str) or not self.model
                or not isinstance(self.binding_key, str) or re.fullmatch(r"[0-9a-f]{64}", self.binding_key) is None
                or type(self.max_generation_calls) is not int or self.max_generation_calls <= 0
                or type(self.max_completion_tokens) is not int or self.max_completion_tokens <= 0
                or type(self.deadline_monotonic) not in (int, float) or not math.isfinite(self.deadline_monotonic)
                or self.deadline_monotonic <= clock()
                or self.execution_kind not in {"controlled_fake_provider", "externally_admitted_wse"}):
            raise ValueError("Explicit new provider condition and bounded external ownership required")


def native_parameters(original):
    """Map only the original single-sample HF parameters with direct WSE fields.

    Pipeline-only fields are retained in the private intent, not sent as API
    parameters. HF truncation is not reproduced: complete native fit is required.
    Other optional HF settings fail closed instead of being silently dropped.
    """
    required = {"max_new_tokens", "temperature", "do_sample", "return_full_text", "truncation", "padding"}
    optional = {"top_p", "top_k", "repetition_penalty", "seed"}
    if type(original) is not dict or not required.issubset(original) or set(original) - required - optional:
        raise ValueError("Unsupported or absent original Pipeline parameter")
    if (type(original["max_new_tokens"]) is not int or original["max_new_tokens"] <= 0
            or type(original["temperature"]) not in (int, float) or not math.isfinite(original["temperature"])
            or original["temperature"] < 0 or type(original["do_sample"]) is not bool
            or original["do_sample"] is not (original["temperature"] > 0)
            or original["return_full_text"] is not False or type(original["truncation"]) is not bool
            or original["padding"] is not False):
        raise ValueError("Unsupported original sampling or Pipeline semantics")
    for name in optional.intersection(original):
        value = original[name]
        if name in {"seed", "top_k"}:
            if type(value) is not int or name == "top_k" and value <= 0:
                raise ValueError("Invalid original integer sampling parameter")
        elif type(value) not in (int, float) or not math.isfinite(value) or value <= 0 or name == "top_p" and value > 1:
            raise ValueError("Invalid original numeric sampling parameter")
    return {name: deepcopy(value) for name, value in original.items()
            if name not in {"do_sample", "return_full_text", "truncation", "padding"}}


class PrivateHTTPRecorder:
    """Delegate the same HTTP once and save available SSE bytes before decoding.

    Tokenization JSON is a parsed observation, not falsely labelled original
    response bytes. The WSE transport already returns original streaming bytes.
    Headers and exception text are deliberately not copied to public metadata.
    """
    def __init__(self, delegate, folder, condition, timeout, *, clock, stream_type):
        self.delegate, self.folder, self.condition = delegate, folder, condition
        self.timeout, self.clock, self.stream_type = timeout, clock, stream_type
        self.entries = []

    def __call__(self, method, route, payload):
        generation = method == "POST" and route == "/v1/chat/completions"
        if method != "POST" or route not in {"/tokenize", "/v1/chat/completions"}:
            raise ValueError("Only original tokenization and one-shot generation routes allowed")
        if self.clock() + self.timeout > self.condition.deadline_monotonic:
            raise ValueError("Insufficient remaining enclosing deadline for unchanged HTTP timeout")
        index = len(self.entries)
        entry = {"ordinal": index, "generation": generation, "dispatch_started": False,
                 "response_received": False, "receipt_saved_privately": False,
                 "http_status": None, "body_complete": None, "exception_class": None}
        self.entries.append(entry)
        _write(self.folder / f"{index:05d}-request.json", _bytes({"method": method, "route": route, "payload": payload}))
        entry["dispatch_started"] = True
        entry["started_monotonic"] = self.clock()
        try:
            status, headers, body = self.delegate(method, route, payload)
            entry.update(response_received=True, http_status=status, returned_body=body)
            if isinstance(body, self.stream_type):
                entry["body_complete"] = body.complete
                entry["response_sha256"] = _sha(body.raw)
                entry["response_bytes"] = len(body.raw)
                _write(self.folder / f"{index:05d}-response.sse", body.raw)
            else:
                raw = _bytes(body)
                entry["response_observation_sha256"] = _sha(raw)
                _write(self.folder / f"{index:05d}-parsed-response-observation.json", raw)
            entry["receipt_saved_privately"] = True
            return status, headers, body
        except BaseException as error:
            entry["exception_class"] = type(error).__name__
            raise
        finally:
            entry["ended_monotonic"] = self.clock()


class WSEPipelineRuntime:
    """One original Pipeline item at a time with a separate native usage ledger."""
    def __init__(self, transport, condition, private_output, *, clock=time.monotonic):
        bridge, wse2, wse, contracts = libraries()
        if not isinstance(transport, wse2.WSETransportV2) or not isinstance(condition, WSEPipelineCondition):
            raise ValueError("Explicit existing WSE V2 transport and new condition required")
        condition.validate(clock)
        binding = transport.inspect_binding(condition.role)
        if (binding.key != condition.binding_key or binding.model != condition.model
                or binding.backend_max_attempts != 1 or not isinstance(binding.single_dispatch_contract_sha256, str)
                or re.fullmatch(r"[0-9a-f]{64}", binding.single_dispatch_contract_sha256) is None
                or type(transport.timeout) not in (int, float) or not math.isfinite(transport.timeout) or transport.timeout <= 0):
            raise ValueError("Exact model, binding and backend single-dispatch contract required")
        output = Path(private_output).absolute()
        resolved = output.resolve()
        if (resolved.is_relative_to(ROOT.resolve()) or resolved.is_relative_to(CORE.resolve())
                or resolved.is_relative_to(Path("/results").resolve())
                or any(v.is_symlink() or getattr(v, "is_junction", lambda: False)() for v in (output, *output.parents))
                or not output.is_dir() or any(output.iterdir())):
            raise ValueError("Fresh private unlinked output outside repository and public results required")
        _private_directory(resolved)
        publisher = private_publication()
        self.output, self.condition, self.clock, self.binding = resolved, condition, clock, binding
        self.bridge, self.wse, self.contracts = bridge, wse, contracts
        self.requested_model, self.tokenizer = condition.model, None
        self.abort_required, self.sequence = False, 0
        self.lock, self.costs = threading.Lock(), []
        self.recorder = PrivateHTTPRecorder(transport.http, output / "private_http", condition,
                                           transport.timeout, clock=clock, stream_type=wse.StreamReceipt)
        # Explicit new instance composition. No mutation of the admitted
        # transport, its HTTP function, module functions or frozen Core bytes.
        self.transport = wse2.WSETransportV2(transport.base_url, transport._token, transport.bindings,
            transport.lease, server=transport.server, queue_binding=transport.queue_binding,
            expected_queue_binding_sha256=transport.queue_binding["sha256"] if transport.queue_binding else None,
            http=self.recorder, timeout=transport.timeout)
        measured_helpers = (bridge, wse2, wse, contracts, publisher, bridge.construction,
            sys.modules["Experiments.strict_autoschemakg.contract"],
            sys.modules["Experiments.strict_autoschemakg.source_imports"])
        if any(not Path(module.__file__).resolve().is_relative_to(CORE.resolve()) for module in measured_helpers):
            raise ValueError("Measured private-writer/native dependency origin differs")
        self.metadata = {"protocol": PROTOCOL, "backend": "vllm_wse_strict_native_pipeline_bridge",
            "condition": asdict(condition), "binding": asdict(binding), "extra_native_json_grammar": False,
            "transport_retries": 0, "native_validation_and_retries": "Unchanged original LLMGenerator, retry3",
            "input_policy": "HF truncation wish logged, complete native input fit or stop",
            "sampling_equivalence": "Explicit kwargs preserved, unspecified backend defaults and special-token equivalence unproven",
            "preflight_costs": "External and not included in this construction-only ledger",
            "hard_supervisor_and_reservation": "Required external ownership, not created by this adapter",
            "private_storage": {"posix_owner_and_mode_verified": os.name == "posix",
                "windows_acl_verified": False, "writer_protocol": publisher.PROTOCOL,
                "windows_acl_policy": "Separate external caller admission required, not certified here"},
            "helper_binding_scope": "Measured helper/dependency bytes, enclosing full closure remains external",
            "model_weights_identity_attested": False,
            "helper_sha256": {Path(m.__file__).relative_to(CORE).as_posix(): _sha(Path(m.__file__).read_bytes())
                              for m in measured_helpers}}
        _write(output / "native_wse_condition.json", _bytes(self.metadata))

    def _book_new_generations(self, from_index):
        for entry in self.recorder.entries[from_index:]:
            if (not entry["generation"] or not entry["dispatch_started"]
                    or any(row["http_ordinal"] == entry["ordinal"] for row in self.costs)):
                continue
            body = entry.get("returned_body")
            decoded = self.wse._stream_result(body) if entry.get("http_status") == 200 else None
            confirmed = decoded is not None and decoded.status == "generated"
            usage = decoded.usage if confirmed else None
            self.costs.append({"http_ordinal": entry["ordinal"], "response_received": entry["response_received"],
                "http_status": entry["http_status"], "provider_terminal_confirmed": confirmed,
                "finish_reason": decoded.finish_reason if confirmed else None,
                "provider_native_usage": deepcopy(usage), "unknown_execution": not confirmed and entry["http_status"] not in
                    {400, 401, 403, 404, 405, 409, 422, 423, 429},
                "receipt_saved_privately": entry["receipt_saved_privately"],
                "response_sha256": entry.get("response_sha256"), "response_bytes": entry.get("response_bytes"),
                "http_client_interval_seconds": entry["ended_monotonic"] - entry["started_monotonic"]})

    def summary(self):
        known = [row["provider_native_usage"] for row in self.costs if row["provider_native_usage"] is not None]
        complete = bool(self.costs) and len(known) == len(self.costs)
        return {"protocol": PROTOCOL, "execution_kind": self.condition.execution_kind,
            "generation_http_attempts": len(self.costs), "metadata_http_attempts": sum(not r["generation"] and r["dispatch_started"] for r in self.recorder.entries),
            "confirmed_terminal_generations": sum(r["provider_terminal_confirmed"] for r in self.costs),
            "unknown_executions": sum(r["unknown_execution"] for r in self.costs),
            "metering_complete": complete, "known_input_token_lower_bound": sum(r["prompt_tokens"] for r in known),
            "known_output_token_lower_bound": sum(r["completion_tokens"] for r in known),
            "input_tokens": sum(r["prompt_tokens"] for r in known) if complete else None,
            "output_tokens": sum(r["completion_tokens"] for r in known) if complete else None,
            "total_tokens": sum(r["total_tokens"] for r in known) if complete else None,
            "thinking_in_output_tokens_once": True, "separate_thinking_tokens": None,
            "provider_gpu_seconds": None, "provider_model_seconds": None, "money_cost": None,
            "preflight_included": False, "preflight_tokens": None,
            "abort_required": self.abort_required, "no_automatic_refund_or_replay": True,
            "source_quality_evaluated": False, "receipts": deepcopy(self.costs)}

    def generate(self, messages, parameters):
        with self.lock:
            index, first_http = self.sequence, len(self.recorder.entries)
            self.sequence += 1
            try:
                if self.abort_required:
                    raise RuntimeError("Unconfirmed or exhausted WSE native condition cannot continue")
                if (not isinstance(messages, list) or not messages or any(type(row) is not dict or
                        set(row) != {"role", "content"} or row["role"] not in {"system", "user", "assistant"}
                        or not isinstance(row["content"], str) for row in messages)):
                    raise ValueError("Original nonempty text message list required")
                original = deepcopy(parameters)
                mapped = native_parameters(original)
                _write(self.output / "native_calls" / f"{index:05d}-intent.json",
                       _bytes({"native_messages": messages, "native_generation_kwargs": original,
                               "mapped_parameters": mapped, "input_truncation_applied": False}))
                binding = self.transport.inspect_binding(self.condition.role)
                if binding.key != self.condition.binding_key:
                    raise ValueError("Frozen runtime binding changed")
                if len(self.costs) >= self.condition.max_generation_calls:
                    raise ValueError("Native generation call cap exhausted")
                used = sum(r["provider_native_usage"]["completion_tokens"] for r in self.costs if r["provider_native_usage"] is not None)
                if mapped["max_new_tokens"] > self.condition.max_completion_tokens - used:
                    raise ValueError("Original output cap exceeds remaining completion budget, no rewriting")
                request = self.contracts.Request(f"native-wse:{index}:" + self.contracts.digest([messages, original]),
                    self.condition.role, deepcopy(messages), None, mapped, PROTOCOL)
                self.transport.output_tokens(request)
                counted = self.transport.count_input(request)
                if not self.transport.fits(request, counted):
                    raise ValueError("Full native input and unchanged output cap do not fit, no truncation")
                self.transport.lease.assert_healthy()
                _write(self.output / "native_calls" / f"{index:05d}-request.json", _bytes(request.wire()))
                result = self.transport.send_once(request)
                self._book_new_generations(first_http)
                _write(self.output / "native_calls" / f"{index:05d}-response.json", _bytes(asdict(result)))
                if (result.status != "generated" or not isinstance(result.raw_response, str)
                        or result.finish_reason not in {"stop", "length"} or result.usage is None
                        or not isinstance(result.response, dict) or result.response.get("model") != binding.model
                        or result.usage["prompt_tokens"] != counted
                        or result.usage["completion_tokens"] > mapped["max_new_tokens"]
                        or not self.costs or not self.costs[-1]["receipt_saved_privately"]
                        or self.costs[-1]["response_sha256"] is None):
                    raise RuntimeError("Native response identity, execution, usage or private evidence unconfirmed")
                # Valid text / empty inventory / format repair / retry ownership
                # remains entirely with the unchanged original generator.
                return result.raw_response
            except BaseException:
                self.abort_required = True
                if not any(r["http_ordinal"] >= first_http for r in self.costs):
                    self._book_new_generations(first_http)
                raise
            finally:
                try:
                    _write(self.output / "native_cost_capsules" / f"{index:05d}.json", _bytes(self.summary()))
                except BaseException:
                    # This occurs even after a successful return was prepared.
                    # The original allow-empty handler must not mistake it for
                    # a completed method result or replay the paid generation.
                    self.abort_required = True
                    raise

    def client(self, *, pipeline_base=None):
        return self.bridge.pipeline_client(self, pipeline_base=pipeline_base)

    def readme_sequence(self, native, *, data_directory, filename_pattern):
        """The existing original README implementation, explicitly extraction only."""
        return self.bridge.readme_sequence(native, self.client(), data_directory=data_directory,
            filename_pattern=filename_pattern, model=self.requested_model, output=self.output, extraction_only=True)

    def construct(self, original_source, *, data_directory, filename_pattern):
        """Preserve the existing pinned source/import guard, no replacement extractor."""
        return self.bridge.construct(original_source, self.client(), data_directory=data_directory,
            filename_pattern=filename_pattern, model=self.requested_model, output=self.output, extraction_only=True)
