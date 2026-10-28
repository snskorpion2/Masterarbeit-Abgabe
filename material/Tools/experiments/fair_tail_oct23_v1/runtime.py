"""Small fail-stop Mantle text callback for already constructed native rows.

Reuses the pinned reader Wire and its native SDK/envelope policy, never run().
Import and initialization do not load credentials or dispatch. The caller owns
authorization, input inventory and the matched AS/AS_A suffix scope.
"""
from copy import deepcopy
from hashlib import sha256
import importlib.util
import json
from pathlib import Path
import sys
from threading import Lock
from types import FunctionType

from Experiments.strict_autoschemakg.immutable_publish import publish_bytes
from Tools.wse.strict_native_wse_pipeline_adapter_oct13_v1 import native_parameters

READER = Path('withheld-artifact/0a3f24b1110de3d8351b')
READER_SHA = "7b727829b90ddacac1ff52c5ee520ab186c63d05021e8c921c65f088b0571065"
MODEL, TIMEOUT = "deepseek.v3.2", 300
PARAMETERS = {"model": MODEL, "max_tokens": 8192, "temperature": 0.7, "stream": False}


class MantleTailHalt(BaseException):
    """Cannot be swallowed by original SDK validation/retry wrappers."""


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"), allow_nan=False).encode("utf8")


def pin(path):
    path = Path(path).absolute()
    if path.is_symlink() or not path.is_file():
        raise ValueError("Regular original artifact required")
    raw = path.read_bytes()
    return {"path": str(path), "bytes": len(raw), "sha256": sha256(raw).hexdigest()}


def save(path, value):
    publish_bytes(path, value if type(value) is bytes else canonical(value), same=lambda _: False)
    return pin(path)


def definitions(path):
    if pin(path)["sha256"] != READER_SHA:
        raise ValueError("Original reader source changed")
    spec = importlib.util.spec_from_file_location("fair_tail_pinned_reader", path)
    reader = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = reader
    spec.loader.exec_module(reader)
    old, policy = reader.definitions()
    return reader, old, policy


def one_wire(reader, old, rows, folder):
    original = reader.Wire.__call__
    namespace = dict(original.__globals__, BASE=folder, HTTP=TIMEOUT)
    isolated = FunctionType(original.__code__, namespace, original.__name__,
                            original.__defaults__, original.__closure__)
    class OneWire(reader.Wire):
        def __call__(self, config, payload, *, timeout):
            if len(self.rows) != 1 or self.attempts:
                raise MantleTailHalt("One physical POST per native callback")
            return isolated(self, config, payload, timeout=timeout)
    return OneWire(old, rows)


class MantleTailRuntime:
    def __init__(self, output, *, max_calls, config=None, reader_path=READER,
                 wire_factory=None):
        if type(max_calls) is not int or max_calls <= 0:
            raise ValueError("Positive explicit physical call ceiling required")
        self.output = Path(output).absolute()
        if any(p.is_symlink() or getattr(p, "is_junction", lambda: False)()
               for p in (self.output, *self.output.parents)) or (self.output / "calls").exists():
            raise ValueError("Fresh unlinked call archive required")
        self.config, self.reader_path, self.wire_factory = config, Path(reader_path), wire_factory
        self.max_calls, self.requested_model, self.tokenizer = max_calls, MODEL, None
        self.abort_required, self.phase, self.receipts, self._lock = False, None, [], Lock()
        self.metadata = {"backend": "AWS_Mantle_native_text_suffix", "model": MODEL,
            "wire_parameters": deepcopy(PARAMETERS), "HTTP_timeout_seconds": TIMEOUT,
            "transport_retries": 0, "reasoning": "absent_provider_default",
            "top_p": "absent", "context_window": None, "weight_revision": None,
            "reader": {"path": str(self.reader_path), "sha256": READER_SHA},
            "construction_prefix_model_may_differ": True,
            "native_schema_prompt_and_parser_unchanged": True}

    def generate(self, messages, native_kwargs):
        with self._lock:
            if self.abort_required:
                raise MantleTailHalt("Previous failure blocks every further send")
            active, row, folder = None, None, None
            try:
                if type(self.max_calls) is not int or len(self.receipts) >= self.max_calls:
                    raise ValueError("Physical callback ceiling reached")
                if (type(messages) is not list or not messages or any(type(m) is not dict
                        or set(m) != {"role", "content"} or m["role"] not in {"system", "user", "assistant"}
                        or type(m["content"]) is not str for m in messages)):
                    raise ValueError("Original native text messages required")
                mapped = native_parameters(native_kwargs)
                if set(mapped) - {"max_new_tokens", "temperature"}:
                    raise ValueError("Additional sampling requires a separate condition")
                reader, old, policy = definitions(self.reader_path)
                folder = self.output / "calls" / f"{len(self.receipts):05d}"
                folder.mkdir(parents=True, exist_ok=False)
                payload = {**deepcopy(PARAMETERS), "messages": deepcopy(messages)}
                request = save(folder / "request.json", canonical(payload))
                row = {"ordinal": len(self.receipts), "phase": self.phase, "status": "not_dispatched",
                    "request": request, "native_parameters": deepcopy(native_kwargs),
                    "actual_wire_parameters": deepcopy(PARAMETERS),
                    "prompt_sha256": sha256(canonical(messages)).hexdigest(),
                    "POST_attempts": 0, "unknown_execution": False, "provider_usage": None,
                    "actual_cost_USD": None, "retries": 0, "native_receipt": None}
                self.receipts.append(row)
                save(folder / "intent.json", row)
                config = self.config or old.probe.Config(reader.URL, old.load_key(), "bedrock-mantle", False)
                if config.url != reader.URL:
                    raise ValueError("Bound Mantle endpoint required")
                rows = [{"request": request}]
                wire = ((self.wire_factory(old, rows, folder)) if self.wire_factory is not None
                        else one_wire(reader, old, rows, folder))
                active = policy.MantleClient(folder / "native", config=config, wire=wire,
                    model=MODEL, expected_response_model=MODEL, timeout=TIMEOUT,
                    thinking=None, max_physical_posts=1)
                active.phase = self.phase
                row.update(status="dispatch_entered", unknown_execution=True)
                response = active.client.chat.completions.create(**payload)
                native = active.receipts[-1]
                raw_path = active.output / native["private_response_body_path"]
                actual_request = active.output / "calls/0000/wire_request.json"
                receipt_path = active.output / "calls/0000/receipt.json"
                raw = pin(raw_path)
                if (wire.attempts != 1 or native.get("POST_attempts") != 1
                        or native.get("unknown_execution") is not False
                        or not native.get("text_completion_confirmed")
                        or raw["sha256"] != native.get("response_sha256")
                        or actual_request.read_bytes() != Path(request["path"]).read_bytes()
                        or pin(actual_request)["sha256"] != request["sha256"]
                        or not receipt_path.is_file()):
                    raise MantleTailHalt("Mandatory actual request/response/receipt differs or missing")
                choice = response.choices[0]
                if choice.finish_reason != "stop" or type(choice.message.content) is not str:
                    raise MantleTailHalt("Original terminal text response required")
                row.update(status="completed", raw_response=raw,
                    actual_request=pin(actual_request), actual_receipt=pin(receipt_path),
                    assistant=save(folder / "assistant-original.utf8", choice.message.content.encode("utf8")))
                return choice.message.content
            except BaseException as error:
                self.abort_required = True
                if row is not None:
                    row.update(status="halted", error_class=type(error).__name__)
                raise MantleTailHalt("Mantle native suffix stopped; no automatic resend") from None
            finally:
                if row is not None:
                    native = active.receipts[-1] if active is not None and active.receipts else None
                    if native is not None:
                        row.update(native_receipt=deepcopy(native), POST_attempts=native.get("POST_attempts"),
                            unknown_execution=native.get("unknown_execution", True),
                            provider_usage=deepcopy(native.get("provider_usage")) or None)
                    try:
                        if active is not None:
                            active.client.close()
                        save(folder / "receipt.json", row)
                    except BaseException:
                        self.abort_required = True
                        raise MantleTailHalt("Durable suffix receipt unconfirmed; no resend") from None
