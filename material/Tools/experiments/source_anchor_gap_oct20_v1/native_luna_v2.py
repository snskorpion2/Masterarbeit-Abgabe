"""Separate native gpt-6-luna condition; no retries or replacement of old runs.

The provider requested max_completion_tokens instead of max_tokens. This new
condition omits temperature rather than claiming the original temperature=0.
Its completion cap includes reasoning tokens. access-only stops before main;
execute requires the completely validated saved access and no main prefix.
"""
from __future__ import annotations

import argparse
from pathlib import Path
import sys
import time
from urllib.error import HTTPError

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from Tools.experiments.source_anchor_gap_oct20_v1 import run_study as runner


MODEL = "gpt-6-luna"
RUN_KEY = "gpt-6-luna-native-v2"
EXTENSION_NAME = "extension-native-luna-v2.json"
CONDITION = {
    "model": MODEL, "run_key": RUN_KEY, "temperature_present": False,
    "token_parameter": "max_completion_tokens", "cap_includes_reasoning": True,
    "cap": 2048, "access_cap": 1024, "spacing_seconds": 12,
    "HTTP_timeout_seconds": 180, "source_view_mask_cells": 24,
    "main_requests": 48, "order": "B,C iff (index // 2) % 2 == 0; otherwise C,B",
    "automatic_retries": 0, "access_mode": "separate_access_only_then_execute",
}
ACCESS_MESSAGES = [{"role": "user", "content": 'Return exactly {"ok":true}.'}]
_ACCESS_ARTIFACTS = (
    "access/request.json", "access/intent.json", "access/provider-response.json",
    "access/receipt.json", "observed-model.json",
)


def _payload(messages, cap):
    return {"model": MODEL, "messages": messages, "max_completion_tokens": cap,
            "stream": False, "n": 1}


def call(config, folder, messages, cap, timeout):
    """One native POST using the original transport, safety and response decoder."""
    folder.mkdir(parents=True, exist_ok=False)
    payload = _payload(messages, cap)
    request = runner.raw_json(payload)
    runner.save(folder / "request.json", request)
    runner.save(folder / "intent.json", runner.raw_json({
        "request_sha256": runner.sha(request), "model": MODEL, "cap": cap,
        "automatic_retries": 0, "endpoint_sha256": runner.sha(config.url.encode())}))
    started = time.monotonic()
    receipt = {"model_requested": MODEL, "status": "unknown_execution",
               "HTTP_status": None, "HTTP_body_complete": False,
               "elapsed_seconds": None, "provider_usage": None}
    try:
        try:
            status, raw, complete = runner.transport.azure_wire(config, payload, timeout=timeout)
        except HTTPError as exc:
            status, raw, complete = exc.code, *runner.transport._read_response(exc)
        receipt.update(HTTP_status=status, HTTP_body_complete=complete,
                       response_bytes=len(raw), response_sha256=runner.sha(raw))
        if complete and status != 200:
            receipt["status"] = "HTTP_rejected"
        runner.accounting.safe_object(raw, config, max_bytes=262144,
                                      strict_json=runner.probe._strict_json)
        runner.save(folder / "provider-response.json", raw)
        if not complete or status != 200:
            receipt["status"] = "HTTP_rejected" if complete and status != 200 else "unknown_execution"
            raise RuntimeError("Provider HTTP response was rejected or incomplete")
        text, native = runner.provider_response(raw, config, cap)
        receipt.update(native)
        tokens = native["provider_usage"]["completion_tokens"]
        if tokens is not None and tokens > cap:
            receipt["status"] = "output_cap_exceeded"
            raise RuntimeError("Provider completion exceeded the reasoning-inclusive cap")
        if native["finish_reason"] != "stop":
            receipt["status"] = "output_incomplete"
            raise RuntimeError("Provider completion did not finish with stop")
        receipt["status"] = "completed"
        return runner.probe._strict_json(text)
    except Exception as exc:
        receipt["error_type"] = type(exc).__name__
        if receipt["status"] == "completed":
            receipt["status"] = "invalid_json"
        raise
    finally:
        receipt["elapsed_seconds"] = round(time.monotonic() - started, 6)
        runner.save(folder / "receipt.json", runner.raw_json(receipt))


def _expected_extension(folder):
    frozen = runner.verify(folder)
    for field in ("cap", "spacing_seconds", "HTTP_timeout_seconds"):
        if frozen[field] != CONDITION[field]:
            raise ValueError("Original source condition has different request bounds")
    if len(runner.read(folder / "cases.json")) != CONDITION["source_view_mask_cells"]:
        raise ValueError("Expected all 24 original source-view/mask cells")
    return {
        "format": "source-anchor-gap-native-model-extension-2",
        "source_freeze_sha256": runner.sha((folder / "freeze.json").read_bytes()),
        "controller_sha256": runner.sha(Path(__file__).read_bytes()),
        "artifact_sha256": frozen["artifact_sha256"], "condition": dict(CONDITION),
    }


def freeze_extension(folder):
    value = _expected_extension(folder)
    runner.save(folder / EXTENSION_NAME, runner.raw_json(value))
    return value


def verify_extension(folder):
    value = runner.read(folder / EXTENSION_NAME)
    if value != _expected_extension(folder):
        raise ValueError("Extension/source/controller binding changed; no dispatch")
    return value


def _extension_hash(folder):
    return runner.sha((folder / EXTENSION_NAME).read_bytes())


def _native_model(receipt):
    model = receipt.get("provider_model")
    if not isinstance(model, str) or not model.strip():
        raise ValueError("A nonempty provider-reported model is required")
    return model


def _access_ok(value):
    return type(value) is dict and set(value) == {"ok"} and value["ok"] is True


def access_only(folder):
    output = folder / "runs" / RUN_KEY
    if output.exists():
        raise FileExistsError("This native model condition already has an execution directory")
    if (folder / EXTENSION_NAME).exists():
        verify_extension(folder)
    else:
        freeze_extension(folder)
    output.mkdir(parents=True, exist_ok=False)
    try:
        config = runner.probe.load_config()
        verify_extension(folder)
        value = call(config, output / "access", ACCESS_MESSAGES,
                     CONDITION["access_cap"], CONDITION["HTTP_timeout_seconds"])
        receipt = runner.read(output / "access/receipt.json")
        if receipt.get("status") != "completed" or not _access_ok(value):
            raise ValueError("Access requires exactly the JSON object {ok:true}")
        native = _native_model(receipt)
        runner.save(output / "observed-model.json", runner.raw_json({
            "requested": MODEL, "reported": native, "weight_revision_attested": False}))
        proof = {"status": "access_complete", "main_requests": 0,
                 "extension_freeze_sha256": _extension_hash(folder),
                 "artifact_sha256": {name: runner.sha((output / name).read_bytes())
                                     for name in _ACCESS_ARTIFACTS}}
        runner.save(output / "access-terminal.json", runner.raw_json(proof))
        print(runner.raw_json({"model": MODEL, "run_key": RUN_KEY, "status": "access_complete",
                              "main_requests": 0, "provider_model": native,
                              "elapsed_seconds": receipt["elapsed_seconds"],
                              "final_text": value}).decode(), flush=True)
    except Exception as exc:
        runner.save(output / "access-terminal.json", runner.raw_json({
            "status": "technical_stop", "error_type": type(exc).__name__,
            "main_requests": 0, "automatic_retry": False,
            "extension_freeze_sha256": _extension_hash(folder)}))
        raise SystemExit(1) from None


def _saved_access(folder, config):
    verify_extension(folder)
    output = folder / "runs" / RUN_KEY
    if {p.name for p in output.iterdir()} != {"access", "observed-model.json", "access-terminal.json"}:
        raise ValueError("Main execution must be wholly unstarted; no prefix replay")
    proof = runner.read(output / "access-terminal.json")
    if (proof.get("status") != "access_complete" or proof.get("main_requests") != 0
            or proof.get("extension_freeze_sha256") != _extension_hash(folder)
            or set(proof.get("artifact_sha256", {})) != set(_ACCESS_ARTIFACTS)):
        raise ValueError("A completely validated saved access is required")
    for name, digest in proof["artifact_sha256"].items():
        if runner.sha((output / name).read_bytes()) != digest:
            raise ValueError("Saved access artifact changed")
    request = runner.raw_json(_payload(ACCESS_MESSAGES, CONDITION["access_cap"]))
    intent = runner.read(output / "access/intent.json")
    receipt = runner.read(output / "access/receipt.json")
    raw = (output / "access/provider-response.json").read_bytes()
    if ((output / "access/request.json").read_bytes() != request
            or intent.get("request_sha256") != runner.sha(request)
            or intent.get("endpoint_sha256") != runner.sha(config.url.encode())
            or intent.get("model") != MODEL or intent.get("cap") != CONDITION["access_cap"]
            or intent.get("automatic_retries") != 0
            or receipt.get("status") != "completed" or receipt.get("HTTP_status") != 200
            or receipt.get("HTTP_body_complete") is not True
            or receipt.get("model_requested") != MODEL
            or receipt.get("response_sha256") != runner.sha(raw)
            or receipt.get("response_bytes") != len(raw)):
        raise ValueError("Saved access request/receipt binding is invalid")
    text, native = runner.provider_response(raw, config, CONDITION["access_cap"])
    tokens = native["provider_usage"]["completion_tokens"]
    if (not _access_ok(runner.probe._strict_json(text)) or native["finish_reason"] != "stop"
            or (tokens is not None and tokens > CONDITION["access_cap"])
            or any(receipt.get(key) != value for key, value in native.items())):
        raise ValueError("Saved access completion does not satisfy its original contract")
    reported = _native_model(receipt)
    if runner.read(output / "observed-model.json") != {
            "requested": MODEL, "reported": reported, "weight_revision_attested": False}:
        raise ValueError("Saved provider model binding changed")
    return reported


def execute(folder):
    config = runner.probe.load_config()
    expected_model = _saved_access(folder, config)
    output = folder / "runs" / RUN_KEY
    runner.save(output / "main-start.json", runner.raw_json({
        "extension_freeze_sha256": _extension_hash(folder), "automatic_retry": False}))
    # Access ran in another process, so wait a full interval before main.
    last_dispatch = time.monotonic()
    completed = []
    try:
        cases = runner.read(folder / "cases.json")
        for index, case in enumerate(cases):
            order = ("B", "C") if (index // 2) % 2 == 0 else ("C", "B")
            for arm in order:
                verify_extension(folder)
                time.sleep(max(0, CONDITION["spacing_seconds"] - (time.monotonic() - last_dispatch)))
                verify_extension(folder)
                target = output / f"cell-{index:03d}-{arm}"
                last_dispatch = time.monotonic()
                reply = call(config, target, runner.study.messages(case["source"], case["base"], arm),
                             CONDITION["cap"], CONDITION["HTTP_timeout_seconds"])
                receipt = runner.read(target / "receipt.json")
                if receipt.get("status") != "completed" or _native_model(receipt) != expected_model:
                    raise ValueError("Provider-reported model/completion changed within the condition")
                runner.save(target / "merged.json", runner.raw_json(runner.study.merge(case["base"], reply)))
                completed.append({"index": index, "case_id": case["case_id"], "world_id": case["world_id"],
                                  "draw_id": case["draw_id"], "arm": arm})
                print(runner.raw_json({"model": MODEL, "run_key": RUN_KEY,
                                      "completed": len(completed), "total": 48}).decode(), flush=True)
        runner.save(output / "terminal.json", runner.raw_json({
            "status": "complete", "completed": completed,
            "extension_freeze_sha256": _extension_hash(folder)}))
    except Exception as exc:
        runner.save(output / "terminal.json", runner.raw_json({
            "status": "technical_stop", "error_type": type(exc).__name__,
            "completed": completed, "automatic_retry": False,
            "extension_freeze_sha256": _extension_hash(folder)}))
        raise SystemExit(1) from None


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("freeze", "verify", "access-only", "execute"))
    parser.add_argument("--private-root", type=Path, required=True)
    args = parser.parse_args()
    folder = args.private_root.resolve()
    if folder.is_relative_to(runner.ROOT) or folder.is_relative_to(runner.ROOT.parent / "Masterarbeit-triple-methods-v1"):
        parser.error("Source-bearing study data must remain outside checkouts")
    {"freeze": freeze_extension, "verify": verify_extension,
     "access-only": access_only, "execute": execute}[args.mode](folder)
