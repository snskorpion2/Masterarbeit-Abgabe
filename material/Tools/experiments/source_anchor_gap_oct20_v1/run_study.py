"""One-shot controlled repair study using existing benchmark and Azure helpers."""

from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import secrets
import sys
import time
from urllib.error import HTTPError

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT), str(ROOT / "Tools/kgc_benchmark"), str(Path(__file__).parent)]

from Tools.azure import probe, accounting, http_failure_probe_v2 as transport
from Tools.azure.output_budget_probe_v2 import provider_response
import study


def raw_json(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def save(path, raw):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as handle:
        handle.write(raw)
        handle.flush()
        os.fsync(handle.fileno())


def read(path):
    return json.loads(path.read_bytes())


def pins():
    import kgcbench.generator, kgcbench.evaluate, kgcbench.adapters, kgcbench.literals
    modules = [study, probe, accounting, transport, kgcbench.generator,
               kgcbench.evaluate, kgcbench.adapters, kgcbench.literals]
    files = [Path(__file__), Path(__file__).with_name("PROTOCOL.md")]
    files += [Path(module.__file__) for module in modules]
    files += [ROOT / "Tools/azure/output_budget_probe_v2.py"]
    files += sorted(Path(kgcbench.generator.__file__).parent.glob("*.py"))
    return {str(path.resolve()): sha(path.read_bytes()) for path in files}


def verify(folder):
    frozen = read(folder / "freeze.json")
    if frozen["code_sha256"] != pins():
        raise ValueError("Bound study/helper bytes changed; no dispatch")
    for name, digest in frozen["artifact_sha256"].items():
        if sha((folder / name).read_bytes()) != digest:
            raise ValueError("Bound source/mask bytes changed; no dispatch")
    return frozen


def prepare(folder):
    folder.mkdir(parents=True, exist_ok=False)
    before = pins()
    save(folder / "method-freeze-before-seeds.json", raw_json({"code_sha256": before}))
    dataset = study.prepare_dataset(secrets.randbits(128))
    cases = study.masked_cases(dataset, secrets.randbits(128))
    save(folder / "dataset.json", raw_json(dataset))
    save(folder / "cases.json", raw_json(cases))
    if pins() != before:
        raise ValueError("Method changed during preparation")
    save(folder / "freeze.json", raw_json({"protocol": "numeric-gap-repair:oct20-v1",
        "code_sha256": before, "models": ["gpt-4.1-mini", "grok-4.7"],
        "cap": 2048, "spacing_seconds": 12, "HTTP_timeout_seconds": 180,
        "artifact_sha256": {name: sha((folder / name).read_bytes())
                            for name in ("dataset.json", "cases.json")}}))
    print(json.dumps({"prepared": True, "worlds": 4, "source_views": 8,
                      "masked_cells": len(cases), "model_calls": 0}))


def call(config, folder, messages, model, cap, timeout):
    folder.mkdir(parents=True, exist_ok=False)
    payload = {"model": model, "messages": messages, "temperature": 0,
               "max_tokens": cap, "stream": False, "n": 1}
    request = raw_json(payload)
    save(folder / "request.json", request)
    save(folder / "intent.json", raw_json({"request_sha256": sha(request),
        "model": model, "cap": cap, "automatic_retries": 0,
        "endpoint_sha256": sha(config.url.encode())}))
    started = time.monotonic()
    receipt = {"model_requested": model, "status": "unknown_execution",
               "HTTP_status": None, "HTTP_body_complete": False,
               "elapsed_seconds": None, "provider_usage": None}
    try:
        try:
            status, raw, complete = transport.azure_wire(config, payload, timeout=timeout)
        except HTTPError as exc:
            status, raw, complete = exc.code, *transport._read_response(exc)
        receipt.update(HTTP_status=status, HTTP_body_complete=complete,
                       response_bytes=len(raw), response_sha256=sha(raw))
        if complete and status != 200:
            receipt["status"] = "HTTP_rejected"
        # Apply the existing credential/reflection gate before retaining bytes.
        accounting.safe_object(raw, config, max_bytes=262144, strict_json=probe._strict_json)
        save(folder / "provider-response.json", raw)
        if not complete or status != 200:
            receipt["status"] = "HTTP_rejected" if complete and status != 200 else "unknown_execution"
            raise RuntimeError("Provider did not return a complete successful response")
        text, native = provider_response(raw, config, cap)
        receipt.update(native)
        completion_tokens = native["provider_usage"]["completion_tokens"]
        if completion_tokens is not None and completion_tokens > cap:
            receipt["status"] = "output_cap_exceeded"
            raise RuntimeError("Provider exceeded the fixed output bound")
        if native["finish_reason"] != "stop":
            receipt["status"] = "output_incomplete"
            raise RuntimeError("Incomplete provider output retained; no retry")
        receipt["status"] = "completed"
        return probe._strict_json(text)
    except Exception as exc:
        receipt["error_type"] = type(exc).__name__
        if receipt["status"] == "completed":
            receipt["status"] = "invalid_json"
        raise
    finally:
        receipt["elapsed_seconds"] = round(time.monotonic() - started, 6)
        save(folder / "receipt.json", raw_json(receipt))


def execute(folder, model):
    frozen = verify(folder)
    if model not in frozen["models"]:
        raise ValueError("Model is outside this frozen condition")
    output = folder / "runs" / model
    output.mkdir(parents=True, exist_ok=False)
    config = probe.load_config()
    last_dispatch = None
    expected_native_model = None
    completed = []

    def invoke(messages, target, cap):
        nonlocal last_dispatch, expected_native_model
        verify(folder)
        if last_dispatch is not None:
            time.sleep(max(0, frozen["spacing_seconds"] - (time.monotonic() - last_dispatch)))
        last_dispatch = time.monotonic()
        value = call(config, target, messages, model, cap, frozen["HTTP_timeout_seconds"])
        observed = read(target / "receipt.json")["provider_model"]
        if expected_native_model is None:
            expected_native_model = observed
            save(output / "observed-model.json", raw_json({
                "requested": model, "reported": observed, "weight_revision_attested": False}))
        elif observed != expected_native_model:
            raise ValueError("Provider-reported model changed within frozen condition")
        return value

    try:
        access = invoke([{"role": "user", "content": 'Return exactly {"ok":true}.'}], output / "access", 1024)
        if access != {"ok": True}:
            raise ValueError("Access/format control failed")
        cases = read(folder / "cases.json")
        for index, case in enumerate(cases):
            order = ("B", "C") if (index // 2) % 2 == 0 else ("C", "B")
            for arm in order:
                target = output / f"cell-{index:03d}-{arm}"
                reply = invoke(study.messages(case["source"], case["base"], arm), target, frozen["cap"])
                merged = study.merge(case["base"], reply)
                save(target / "merged.json", raw_json(merged))
                completed.append({"index": index, "case_id": case["case_id"],
                                  "world_id": case["world_id"], "draw_id": case["draw_id"], "arm": arm})
                print(json.dumps({"model": model, "completed": len(completed), "total": len(cases) * 2}), flush=True)
        save(output / "terminal.json", raw_json({"status": "complete", "completed": completed}))
    except Exception as exc:
        save(output / "terminal.json", raw_json({"status": "technical_stop", "error_type": type(exc).__name__,
             "completed": completed, "automatic_retry": False}))
        print(json.dumps({"model": model, "status": "technical_stop", "error_type": type(exc).__name__,
                          "completed_cells": len(completed)}), flush=True)
        raise SystemExit(1) from None


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("prepare", "execute", "verify"))
    parser.add_argument("--private-root", type=Path, required=True)
    parser.add_argument("--model")
    args = parser.parse_args()
    folder = args.private_root.resolve()
    if folder.is_relative_to(ROOT) or folder.is_relative_to(ROOT.parent / "Masterarbeit-triple-methods-v1"):
        parser.error("Source-bearing study data must be outside checkouts")
    if args.mode == "prepare":
        prepare(folder)
    elif args.mode == "verify":
        verify(folder)
        print("All study and artifact bindings match; zero provider calls")
    else:
        execute(folder, args.model)
