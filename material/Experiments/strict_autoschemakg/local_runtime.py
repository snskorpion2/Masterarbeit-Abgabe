"""Explicit local model binding. Never rewrites native prompts or model answers.

Ollama receives a raw prompt rendered by the pinned HF tokenizer. Construction
continues through the ORIGINAL Pipeline branch, including its own validation
and retries. No inference libraries or network operations at module import.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import os
from pathlib import Path
import threading
import time
from types import SimpleNamespace
from urllib.request import Request, urlopen

from .contract import write_json

PROFILES = {
    "nvidia/NVIDIA-Nemotron-3-Nano-4B-BF16": {
        "ollama_model": "nemotron-3-nano:4b",
        "ollama_digest": "6cc467f054393a55e98a74098abde0c762ffb6d1d8cd64becf30458f38886197",
        "tokenizer": "nvidia/NVIDIA-Nemotron-3-Nano-4B-BF16",
        "revision": "dfaf35de3e30f1867dd8dbc38a7fc9fb52d3914f",
        # Pinned HF generation_config: temperature 1, top_p .95. Other
        # sampling values below are Transformers GenerationConfig defaults.
        "defaults": {"temperature": 1.0, "top_p": 0.95, "top_k": 50},
        "transport": "llama_cpp_hf_token_ids",
        "runtime_end_token_ids": [2, 11],
        "hf_generation_config_eos_token_id": 2,
        "hf_tokenizer_eos_token_id": 11,
    },
    "Qwen/Qwen3.5-4B": {
        "ollama_model": "qwen3.5:4b-q4_K_M",
        "ollama_digest": "2a654d98e6fba55d452b7043684e9b57a947e393bbffa62485a7aac05ee4eefd",
        "tokenizer": "Qwen/Qwen3.5-4B",
        "revision": "851bf6e806efd8d0a36b00ddf55e13ccb7b8cd0a",
        # Explicit local provider defaults for original evaluation requests
        # that set no sampling arguments. These are NOT DeepSeek V3 defaults.
        "defaults": {"temperature": 1.0, "top_p": 1.0, "top_k": 50},
    },
}
BASE_URL = "http://127.0.0.1:11434"
CONTEXT = 16384
ALLOWED_CONTEXTS = (16384, 32768, 65536, 131072, 262144)


def validate_context(context, model=None):
    """Allow only reviewed local profiles, below the pinned GGUF context limit."""
    if type(context) is not int or context not in ALLOWED_CONTEXTS:
        raise ValueError("Unsupported local context capacity")
    if model is not None and model not in PROFILES:
        raise ValueError("Local binding requires a registered, pinned model profile")
    return context


def request_json(route, payload=None):
    data = None if payload is None else json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = Request(BASE_URL + route, data=data, headers={"Content-Type": "application/json"})
    with urlopen(request, timeout=1200) as response:
        return json.load(response)


def generation_options(parameters, defaults, context):
    """Translate only explicitly supported native HF arguments, fail otherwise."""
    supported = {"max_new_tokens", "temperature", "do_sample", "top_p", "top_k",
                 "repetition_penalty", "return_full_text", "truncation", "padding"}
    unknown = set(parameters) - supported
    if unknown:
        raise ValueError("Unmapped generation parameters: " + ", ".join(sorted(unknown)))
    if parameters.get("return_full_text", False) or parameters.get("padding", False):
        raise ValueError("Only generated text without batch padding is supported")
    options = {"num_ctx": context, "temperature": defaults.get("temperature", 1.0),
               "top_p": defaults.get("top_p", 1.0), "top_k": defaults.get("top_k", 50),
               "min_p": 0.0, "repeat_penalty": 1.0, "presence_penalty": 0.0,
               "frequency_penalty": 0.0, "stop": []}
    for native, local in (("max_new_tokens", "num_predict"), ("temperature", "temperature"),
                          ("top_p", "top_p"), ("top_k", "top_k"),
                          ("repetition_penalty", "repeat_penalty")):
        if native in parameters:
            options[local] = parameters[native]
    if parameters.get("do_sample") is False:
        options["temperature"] = 0.0
    return options


def render_request(tokenizer, messages, context, reserve, *, safety_tokens=0):
    prompt = tokenizer.apply_chat_template(
        messages, tokenize=False, add_generation_prompt=True, enable_thinking=False,
    )
    count = len(tokenizer.encode(prompt, add_special_tokens=False))
    if type(reserve) is not int or reserve <= 0 or type(safety_tokens) is not int or safety_tokens < 0:
        raise ValueError("Invalid output reserve or safety tokens")
    if count + reserve + safety_tokens > context:
        if safety_tokens:
            raise ValueError(f"Full request exceeds local context: {count} + {reserve} + {safety_tokens} > {context}")
        raise ValueError(f"Full request exceeds local context: {count} + {reserve} > {context}")
    return prompt, count


class LocalOllama:
    def __init__(self, model, output, *, context=CONTEXT, keep_alive="10m"):
        self.context = validate_context(context, model)
        self.keep_alive = keep_alive
        from transformers import AutoTokenizer
        self.profile = PROFILES[model]
        self.name = self.profile["ollama_model"]
        self.requested_model = model
        self.output = Path(output)
        self.lock = threading.Lock()
        self.inference_dispatched = False
        self.tokenizer = AutoTokenizer.from_pretrained(
            self.profile["tokenizer"], revision=self.profile["revision"], trust_remote_code=False,
        )
        show = request_json("/api/show", {"model": self.name})
        tags = request_json("/api/tags")["models"]
        tag = next(item for item in tags if item["name"] == self.name)
        if show["details"]["quantization_level"] != "Q4_K_M":
            raise ValueError("Expected Q4_K_M model, refusing a different quantization")
        self.digest = tag["digest"]
        if self.digest != self.profile["ollama_digest"]:
            raise ValueError("Local model digest differs from the pinned profile")
        gguf_context = [value for key, value in show["model_info"].items()
                        if key.endswith(".context_length")]
        if self.context != CONTEXT and (len(gguf_context) != 1 or type(gguf_context[0]) is not int
                                        or self.context > gguf_context[0]):
            raise ValueError("Requested context exceeds or cannot verify pinned GGUF context limit")
        # Record model and template provenance before any inference.
        self.metadata = {
            "backend": "ollama_raw_with_hf_template", "model": model,
            "model_digest": self.digest, "model_size_bytes": tag["size"],
            "server_version": request_json("/api/version")["version"],
            "profile": self.profile, "context_tokens": self.context, "enable_thinking": False,
            "model_details": show["details"], "gguf_model_info": show["model_info"],
            "packaged_model_parameters": show.get("parameters"),
            "hf_chat_template_sha256": hashlib.sha256(
                json.dumps(self.tokenizer.chat_template, sort_keys=True).encode()).hexdigest(),
            "sampler_defaults": generation_options({}, self.profile["defaults"], self.context),
            "provider_defaults_are_local_not_original_paper_model": True,
            "evaluation_output_limit": "remaining context, no additional token cap",
            "extra_json_grammar": False, "transport_retries": 0,
            "batch_transport": "serial, original order preserved",
        }
        self.server = None
        if keep_alive != "10m":
            self.metadata["keep_alive"] = keep_alive
        if self.profile.get("transport") == "llama_cpp_hf_token_ids":
            from .nemotron_server import NemotronServer
            self.server = (NemotronServer(self.output) if self.context == CONTEXT
                           else NemotronServer(self.output, context=self.context))
            self.metadata["backend"] = "llama_cpp_with_hf_token_ids"
            self.metadata["tokenizer_binding"] = (
                "Pinned HF token IDs, bypassing incompatible GGUF pre-tokenizer. "
                "Model tensor bytes and original messages unchanged."
            )
        write_json(self.output / "local_runtime.json", self.metadata)

    def generate(self, messages, parameters, *, json_schema=None, request_identity=None,
                 adaptive_output_v2=False):
        context = getattr(self, "context", CONTEXT)
        options = generation_options(parameters, self.profile["defaults"], context)
        if adaptive_output_v2:
            model_info = getattr(self, "metadata", {}).get("gguf_model_info", {})
            gguf_context = [value for key, value in model_info.items() if key.endswith(".context_length")]
            if len(gguf_context) != 1 or type(gguf_context[0]) is not int or context > gguf_context[0]:
                raise ValueError("Adaptive output v2 requires verified pinned model context")
        if adaptive_output_v2 and ("num_predict" not in options or type(options["num_predict"]) is not int
                                   or options["num_predict"] <= 0):
            raise ValueError("Adaptive output v2 requires an explicit positive output limit")
        reserve = options.get("num_predict", 1)
        if type(adaptive_output_v2) is not bool:
            raise ValueError("Invalid adaptive output runtime setting")
        prompt, count = render_request(self.tokenizer, messages, context, reserve,
                                       safety_tokens=256 if adaptive_output_v2 else 0)
        if "num_predict" not in options:
            options["num_predict"] = context - count
        payload = {"model": self.name, "prompt": prompt, "raw": True,
                   "stream": False, "think": False, "keep_alive": getattr(self, "keep_alive", "10m"), "options": options}
        if json_schema is not None:
            if not isinstance(json_schema, dict):
                raise ValueError("JSON schema must be an object")
            payload["format"] = json_schema
            metadata = getattr(self, "metadata", None)
            if isinstance(metadata, dict) and not metadata.get("extra_json_grammar"):
                metadata.update(extra_json_grammar=True,
                                decoding_contract="explicit per-call JSON schema, locally validated by caller")
                write_json(self.output / "local_runtime.json", metadata)
        # Serial transport avoids parallel KV allocations. No batch is omitted.
        with self.lock:
            started = time.perf_counter()
            record = {
                "model": self.name, "messages": messages, "rendered_prompt": prompt,
                "options": options, "hf_prompt_tokens": count, "inference_dispatched": False,
            }
            if adaptive_output_v2:
                record["adaptive_output_v2"] = True
            if json_schema is not None:
                record["decoding_contract"] = {"json_schema": json_schema}
            if request_identity is not None:
                record["request_identity"] = request_identity
            try:
                server = getattr(self, "server", None)
                if server is None:
                    record["inference_dispatched"] = True
                    self.inference_dispatched = True
                    response = request_json("/api/generate", payload)
                else:
                    tokens = self.tokenizer.encode(prompt, add_special_tokens=False)
                    record["hf_prompt_token_ids"] = tokens
                    response = (server.generate(tokens, options, json_schema=json_schema)
                                if json_schema is not None else server.generate(tokens, options))
                    response["model"] = self.name
                record["response"] = response
            except Exception as exc:
                from .retry_policy import transient_transport
                record["transport_error"] = {"type": type(exc).__name__, "message": str(exc),
                                             "retryable_transient": transient_transport(exc)}
                if server is not None and isinstance(getattr(server, "last_raw_response", None), dict):
                    record["original_server_response"] = server.last_raw_response
                raise
            finally:
                if server is not None:
                    record["inference_dispatched"] = getattr(server, "last_dispatch_started", False) is True
                    if record["inference_dispatched"]:
                        self.inference_dispatched = True
                record["elapsed_seconds"] = time.perf_counter() - started
                with (self.output / "calls.jsonl").open("a", encoding="utf-8") as stream:
                    stream.write(json.dumps(record, ensure_ascii=False) + "\n")
                    stream.flush()
                    os.fsync(stream.fileno())
        if response.get("model") != self.name or not response.get("done"):
            raise RuntimeError("Unexpected model or incomplete local response")
        # A mismatch can indicate tokenizer drift or silent truncation. Never
        # silently accept the result as a valid baseline request.
        if response.get("prompt_eval_count") != count:
            raise RuntimeError(f"Tokenizer/count mismatch: HF={count}, runtime={response.get('prompt_eval_count')}")
        if response.get("thinking"):
            raise RuntimeError("Thinking output despite explicitly disabled thinking")
        content = response.get("response")
        if not isinstance(content, str):
            raise RuntimeError("Missing text response")
        return content

    def close(self):
        server = getattr(self, "server", None)
        if server is not None:
            server.close()

    def completion(self, **kwargs):
        extra = set(kwargs) - {"model", "messages", "temperature", "max_tokens"}
        if extra:
            raise ValueError("Unmapped native SDK arguments: " + ", ".join(sorted(extra)))
        if kwargs["model"] != self.requested_model:
            raise ValueError("Evaluator requested a different model")
        parameters = {}
        if "temperature" in kwargs:
            parameters["temperature"] = kwargs["temperature"]
        if "max_tokens" in kwargs:
            parameters["max_new_tokens"] = kwargs["max_tokens"]
        text = self.generate(kwargs["messages"], parameters)
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=text))])

    def sdk_factory(self, asynchronous=False, bind_model=False, mcq_json_fence_bridge=False):
        def create(**kwargs):
            if bind_model:
                kwargs["model"] = self.requested_model
            response = self.completion(**kwargs)
            if mcq_json_fence_bridge:
                from .mcq_format import remove_json_fence_label
                original = response.choices[0].message.content
                adapted, audit = remove_json_fence_label(original)
                if audit is not None:
                    response.choices[0].message.content = adapted
                    with self.lock:
                        with (self.output / "format_bridges.jsonl").open("a", encoding="utf-8") as stream:
                            stream.write(json.dumps(audit, ensure_ascii=False) + "\n")
            return response

        async def async_create(**kwargs):
            return await asyncio.to_thread(create, **kwargs)

        def factory(*args, **kwargs):
            return SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(
                create=async_create if asynchronous else create,
            )))
        return factory


def local_pipeline(model, output):
    """Satisfy original Pipeline dispatch without loading HF model weights."""
    from transformers import Pipeline
    runtime = LocalOllama(model, output)

    class TransportPipeline(Pipeline):
        def __init__(self):
            self.tokenizer = runtime.tokenizer
            self.model = None
            self.local_runtime = runtime

        def _sanitize_parameters(self, **kwargs):
            raise NotImplementedError

        def preprocess(self, inputs, **kwargs):
            raise NotImplementedError

        def _forward(self, model_inputs, **kwargs):
            raise NotImplementedError

        def postprocess(self, model_outputs, **kwargs):
            raise NotImplementedError

        def __call__(self, batch_messages, **kwargs):
            return [[{"generated_text": runtime.generate(messages, kwargs)}]
                    for messages in batch_messages]

    return TransportPipeline()
