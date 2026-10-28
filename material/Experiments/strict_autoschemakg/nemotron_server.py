"""Owned llama-server transport for exact, externally tokenized Nemotron prompts.

The original GGUF and the existing Ollama service are never modified. Pure
integer /completion prompts bypass GGUF pre-tokenization and automatic BOS.
API contract: bundled llama.cpp 0.4.1-dev, commit 161755f29.
"""
from __future__ import annotations

import atexit
import hashlib
import json
import os
from pathlib import Path
import socket
import subprocess
import threading
import time
from urllib.error import HTTPError, URLError
from urllib.request import ProxyHandler, Request, build_opener
import uuid


MODEL_SHA256 = "527db2cf6c705d8fabb95693d038d9c06b4a2b0b8b0a4bbdbd01212d37242970"


def sha256_file(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def completion_payload(token_ids, options, context, *, json_schema=None):
    """Translate only the supported transport options, without prompt repair."""
    if not isinstance(token_ids, list) or not token_ids or any(
        type(token) is not int or token < 0 for token in token_ids
    ):
        raise ValueError("prompt must be a nonempty list of nonnegative integer token IDs")
    supported = {"num_ctx", "num_predict", "temperature", "top_p", "top_k",
                 "min_p", "repeat_penalty", "presence_penalty", "frequency_penalty", "stop"}
    unknown = set(options) - supported
    if unknown:
        raise ValueError("Unmapped llama-server options: " + ", ".join(sorted(unknown)))
    if options.get("num_ctx", context) != context:
        raise ValueError("Request context differs from the server context")
    limit = options.get("num_predict")
    if type(limit) is not int or limit <= 0:
        raise ValueError("A positive, explicit num_predict is required")
    if len(token_ids) + limit > context:
        raise ValueError("Prompt and output reservation exceed the server context")
    payload = {
        "prompt": list(token_ids), "n_predict": limit, "stream": False,
        "cache_prompt": True, "return_tokens": True,
        "temperature": 1.0, "top_p": 0.95, "top_k": 50, "min_p": 0.0,
        "repeat_penalty": 1.0, "presence_penalty": 0.0, "frequency_penalty": 0.0,
        "repeat_last_n": context, "stop": [], "typical_p": 1.0,
        "dry_multiplier": 0.0, "xtc_probability": 0.0, "mirostat": 0,
        # Match HF warper order. Temperature before top-p matters numerically.
        "samplers": ["penalties", "temperature", "top_k", "top_p", "min_p"],
    }
    payload.update({key: value for key, value in options.items()
                    if key not in {"num_ctx", "num_predict"}})
    if json_schema is not None:
        if not isinstance(json_schema, dict):
            raise ValueError("JSON schema must be an object")
        payload["json_schema"] = json_schema
    return payload


class NemotronServer:
    """Start/stop only this object's child process, never an existing service."""

    def __init__(self, output, model_path=None, executable=None, *,
                 model="nemotron-3-nano:4b", port=11435, context=16384,
                 startup_timeout=240.0, request_timeout=1200.0):
        model_root = Path(os.environ.get("OLLAMA_MODELS", Path.home() / ".ollama" / "models"))
        install_root = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
        self.model_path = Path(model_path or model_root / "blobs" / ("sha256-" + MODEL_SHA256)).resolve()
        self.executable = Path(executable or install_root / "Programs" / "Ollama" / "lib" / "ollama" / "llama-server.exe").resolve()
        self.output = Path(output)
        if type(port) is not int or not 1 <= port <= 65535 or type(context) is not int or context <= 0:
            raise ValueError("Invalid local server port or context")
        self.model, self.port, self.context = model, port, context
        self.startup_timeout, self.request_timeout = startup_timeout, request_timeout
        self.alias = "strict-nemotron-" + uuid.uuid4().hex
        self.base_url = f"http://127.0.0.1:{port}"
        self.log_path = self.output / (self.alias + ".log")
        self.metadata_path = self.output / (self.alias + ".json")
        self.metadata = {}
        self.process = None
        self._log = None
        self._ready = False
        self._registered = False
        self._closed = False
        self._lock = threading.RLock()

    def preflight(self):
        """Only read files and test port availability. Do not start a process."""
        if not self.executable.is_file() or not self.model_path.is_file():
            raise FileNotFoundError("Pinned llama-server executable or Nemotron GGUF is missing")
        digest = sha256_file(self.model_path)
        if digest != MODEL_SHA256:
            raise ValueError("Nemotron GGUF SHA256 differs from the pinned blob")
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
            if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
                listener.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
            try:
                listener.bind(("127.0.0.1", self.port))
            except OSError as exc:
                raise RuntimeError(f"Port {self.port} is already occupied, refusing to attach") from exc
        return {"model_path": str(self.model_path), "model_sha256": digest,
                "executable": str(self.executable), "executable_sha256": sha256_file(self.executable),
                "context_tokens": self.context, "host": "127.0.0.1", "port": self.port,
                "transport": "llama_completion_integer_token_ids", "transport_retries": 0,
                "alias": self.alias, "log_path": str(self.log_path)}

    def request_json(self, route, payload=None, *, timeout=None):
        """One HTTP attempt, with no system proxy for the loopback endpoint."""
        data = None if payload is None else json.dumps(payload, ensure_ascii=False).encode("utf-8")
        request = Request(self.base_url + route, data=data, headers={"Content-Type": "application/json"})
        try:
            with build_opener(ProxyHandler({})).open(
                request, timeout=self.request_timeout if timeout is None else timeout,
            ) as response:
                return json.load(response)
        except HTTPError as exc:
            # This endpoint is our own loopback-only child, not a credentialed provider.
            if route == "/completion":
                detail = exc.read().decode("utf-8", errors="replace")
                raise RuntimeError(f"Local completion HTTP {exc.code}: {detail}") from exc
            raise

    def _write_metadata(self):
        self.metadata_path.write_text(json.dumps(self.metadata, indent=2) + "\n", encoding="utf-8")

    def start(self):
        with self._lock:
            if self._closed:
                raise RuntimeError("This owned server has already been closed")
            if self._ready:
                if self.process.poll() is not None:
                    raise RuntimeError("Owned llama-server exited")
                return self
            self.metadata = self.preflight()
            self.output.mkdir(parents=True, exist_ok=True)
            command = [str(self.executable), "--model", str(self.model_path),
                       "--host", "127.0.0.1", "--port", str(self.port),
                       "--ctx-size", str(self.context), "--n-gpu-layers", "99",
                       "--parallel", "1", "--no-context-shift", "--no-webui",
                       "--alias", self.alias, "--log-verbosity", "4"]
            self.metadata.update(command=command, status="starting")
            self._write_metadata()
            started = time.perf_counter()
            try:
                self._log = self.log_path.open("xb")
                gpu_directory = self.executable.parent / "cuda_v12"
                gpu_backend = gpu_directory / "ggml-cuda.dll"
                if not gpu_backend.is_file():
                    raise FileNotFoundError("Bundled CUDA backend is missing")
                child_env = dict(os.environ)
                child_env["PATH"] = os.pathsep.join([
                    str(self.executable.parent), str(gpu_directory), child_env.get("PATH", ""),
                ])
                child_env["GGML_BACKEND_PATH"] = str(gpu_backend)
                self.metadata["cuda_backend"] = str(gpu_backend)
                self.metadata["cuda_backend_sha256"] = sha256_file(gpu_backend)
                self.process = subprocess.Popen(
                    command, stdin=subprocess.DEVNULL, stdout=self._log,
                    stderr=subprocess.STDOUT, cwd=str(self.executable.parent),
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                    env=child_env,
                )
                atexit.register(self.close)
                self._registered = True
                self.metadata["pid"] = self.process.pid
                while time.perf_counter() - started < self.startup_timeout:
                    if self.process.poll() is not None:
                        raise RuntimeError(f"Owned llama-server exited during startup. See {self.log_path}")
                    try:
                        health = self.request_json("/health", timeout=1.0)
                    except (HTTPError, URLError, TimeoutError, ConnectionError):
                        time.sleep(0.2)
                        continue
                    if health.get("status") == "ok":
                        models = self.request_json("/v1/models", timeout=2.0)
                        if self.alias not in {entry.get("id") for entry in models.get("data", [])}:
                            raise RuntimeError("Endpoint is not this owned server's unique model alias")
                        self._ready = True
                        self.metadata.update(status="ready", startup_seconds=time.perf_counter() - started)
                        self._write_metadata()
                        return self
                    time.sleep(0.2)
                raise TimeoutError(f"Owned llama-server startup timed out. See {self.log_path}")
            except BaseException:
                self.close()
                raise

    def generate(self, token_ids, options, *, json_schema=None):
        self.last_raw_response = None
        self.last_dispatch_started = False
        payload = completion_payload(token_ids, options, self.context, json_schema=json_schema)
        with self._lock:
            self.start()
            started = time.perf_counter()
            self.last_dispatch_started = True
            result = self.request_json("/completion", payload)
            self.last_raw_response = result
            elapsed = time.perf_counter() - started
            if not isinstance(result, dict) or "error" in result:
                raise RuntimeError("Invalid llama-server completion response")
            if result.get("truncated"):
                raise RuntimeError("llama-server unexpectedly truncated the context")
            if result.get("tokens_evaluated") != len(token_ids):
                raise RuntimeError("llama-server prompt token count differs from the supplied IDs")
            if result.get("stop_type") not in {"eos", "word", "limit"} or result.get("stop") is False:
                raise RuntimeError("Incomplete llama-server completion")
            if not isinstance(result.get("content"), str):
                raise RuntimeError("Missing llama-server text output")
            timings = result.get("timings", {})
            return {
                "model": self.model, "done": True, "response": result["content"],
                "done_reason": "length" if result["stop_type"] == "limit" else "stop",
                # tokens_evaluated is the complete input, not timings.prompt_n
                # which only counts uncached processing on warm requests.
                "prompt_eval_count": result["tokens_evaluated"],
                # tokens_cached is the final slot state, which can include
                # generated tokens. timings.cache_n counts reused input.
                "prompt_eval_cached_count": timings.get("cache_n", 0),
                "eval_count": result.get("tokens_predicted", timings.get("predicted_n")),
                "prompt_eval_duration": round(timings.get("prompt_ms", 0) * 1_000_000),
                "eval_duration": round(timings.get("predicted_ms", 0) * 1_000_000),
                "total_duration": round(elapsed * 1_000_000_000),
                "original_server_response": result,
            }

    def close(self):
        with self._lock:
            process = self.process
            if process is not None and process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=10)
            self.process = None
            self._ready = False
            self._closed = True
            if self._log is not None:
                self._log.close()
                self._log = None
            if self._registered:
                atexit.unregister(self.close)
                self._registered = False
            if self.metadata:
                self.metadata["status"] = "closed"
                self._write_metadata()

    def __enter__(self):
        return self.start()

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()
