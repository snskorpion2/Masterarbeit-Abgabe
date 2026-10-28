"""Isolated, bounded continuation of four failed legacy confidence batches.

Never regenerates a request, changes an original run, or selects on score.
Preparation and reporting are offline. Only --run can dispatch model calls.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
import json
import os
import time
from pathlib import Path

from . import reliability_v2 as r
from .contract import sha256, write_json
from .local_runtime import LocalOllama, generation_options, render_request

VARIANT = "local_lamport_retry_100_v1"
MODEL = r.pilot.CONSTRUCTOR
MAX_ATTEMPTS = 101
CAPS = (1, 2, 3, 5, 10, 20, 50, 101)
TARGETS = tuple(f"c1:nemotron-confidence:{n:05d}" for n in (1, 5, 14, 17))
DEFAULT_SOURCE = Path(__file__).resolve().parents[1] / "results/strict_autoschemakg/local_lamport_repair_v2"
DEFAULT_OUTPUT = DEFAULT_SOURCE.with_name("local_lamport_retry_100_v1")


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def indexed(rows, field):
    result = {row[field]: row for row in rows}
    if len(result) != len(rows):
        raise ValueError(f"Duplicate {field}")
    return result


def costs(calls):
    result = {"raw_transport_records": len(calls), "physical_inference_dispatches": 0,
              "logical_prompt_tokens": 0, "cached_prompt_tokens": 0, "uncached_prompt_tokens": 0,
              "output_tokens": 0, "elapsed_seconds": 0.0, "backend_duration_seconds": 0.0,
              "calls_without_token_usage": 0}
    for call in calls:
        result["physical_inference_dispatches"] += call.get("inference_dispatched") is True
        response = call.get("response", {})
        prompt, cached = response.get("prompt_eval_count"), response.get("prompt_eval_cached_count", 0)
        if type(prompt) is int and type(cached) is int:
            result["logical_prompt_tokens"] += prompt
            result["cached_prompt_tokens"] += cached
            result["uncached_prompt_tokens"] += prompt - cached
        else:
            result["calls_without_token_usage"] += 1
        result["output_tokens"] += response.get("eval_count") or 0
        result["elapsed_seconds"] += call.get("elapsed_seconds", 0)
        result["backend_duration_seconds"] += (response.get("total_duration") or 0) / 1e9
    return result


def first_valid(records, cap=MAX_ATTEMPTS):
    return next((record for record in records if record["attempt_number"] <= cap and record["status"] == "valid"), None)


def check_group(group):
    request = group["request"]
    if request["kind"] != "confidence" or "confidence_protocol" in request or request.get("skip_reason"):
        raise ValueError("Continuation requires unchanged legacy confidence requests")
    if r.schema_for(request) != group["schema"]:
        raise ValueError("Saved legacy schema differs from frozen classifier")


def classified(request, call, model):
    result = r._from_transport(request, call, model)
    if result["status"] == "invalid_format":
        try:
            r.classify(request, result["raw_response"])
        except (ValueError, TypeError, KeyError) as exc:
            result["validation_error"] = {"type": type(exc).__name__, "message": str(exc)}
        try:
            parsed = r.measure.parse_json_response(result["raw_response"])
        except (ValueError, TypeError, KeyError):
            result["diagnostic"] = {"category": "invalid_json_or_container"}
        else:
            items = parsed.get("judgments")
            if request["kind"] == "confidence" and isinstance(items, list):
                ids = [x.get("id") for x in items if isinstance(x, dict) and isinstance(x.get("id"), str)]
                result["diagnostic"] = {"category": "confidence_ids_or_values",
                    "missing_ids": sorted(set(request["item_ids"]) - set(ids)),
                    "additional_ids": sorted(set(ids) - set(request["item_ids"])),
                    "duplicate_ids": sorted({ident for ident in ids if ids.count(ident) > 1})}
            else:
                result["diagnostic"] = {"category": "schema_or_value"}
    return result


def evaluate(group, call, number, runtime_error=None):
    request = group["request"]
    if call.get("messages") != r._request_messages(request) or call.get("decoding_contract", {}).get("json_schema") != group["schema"]:
        raise ValueError("Raw call prompt/schema differs from frozen request")
    for key in ("options", "hf_prompt_tokens"):
        if key in group and call.get(key) != group[key]:
            raise ValueError(f"Raw call {key} drift")
    if "rendered_prompt_sha256" in group and r.artifacts.digest(call.get("rendered_prompt")) != group["rendered_prompt_sha256"]:
        raise ValueError("Rendered prompt drift")
    if "token_ids_sha256" in group and r.artifacts.digest(call.get("hf_prompt_token_ids")) != group["token_ids_sha256"]:
        raise ValueError("HF token IDs drift")
    result = classified(request, call, MODEL)
    if runtime_error is not None:
        result["runtime_error"] = runtime_error
        if result["status"] == "valid":
            result.update(status="transport_error", retry_allowed=False)
    result.update(attempt_number=number, attempt_id=request["request_id"] + f":attempt:{number}")
    return result


def baseline(source):
    """Reclassify every original logical request, preserving every paid physical call."""
    source = Path(source).resolve()
    summary = load(source / "technical_summary.json")
    if summary["preflight"]["variant"] != "local_lamport_reliability_v2":
        raise ValueError("Only the original legacy v2 run is in scope")
    requests, records, raw_calls, files, groups = {}, {}, [], [source / "technical_summary.json"], []
    for relative, expected in summary["artifact_hashes"].items():
        path = (source / relative).resolve()
        if source not in path.parents or sha256(path) != expected:
            raise ValueError(f"Original run artifact changed: {relative}")
        files.append(path)
    for schedule_path in sorted((source / "c1").glob("*/schedule.json")):
        folder = schedule_path.parent
        schedule = load(schedule_path)
        calls = r.pilot._records(folder / "calls.jsonl")
        raw = indexed(calls, "request_identity")
        attempts = r.pilot._records(folder / "attempts.jsonl")
        indexed(attempts, "attempt_id")
        intents = indexed(r.pilot._records(folder / "dispatch_intents.jsonl"), "attempt_id")
        raw_calls.extend(calls)
        files.extend(folder / name for name in ("schedule.json", "attempts.jsonl", "calls.jsonl", "dispatch_intents.jsonl", "final_responses.json", "local_runtime.json"))
        files.extend(folder.glob("strict-nemotron-*.json"))
        for request in schedule["requests"]:
            rid = request["request_id"]
            if rid in requests:
                raise ValueError("Duplicate source request")
            requests[rid] = request
            old = sorted((x for x in attempts if x["request_id"] == rid), key=lambda x: x["attempt_number"])
            if [x["attempt_number"] for x in old] not in ([1], [1, 2]):
                raise ValueError("Unexpected source attempt sequence")
            records[rid] = []
            for entry in old:
                call = raw[entry["attempt_id"]]
                intent = intents[entry["attempt_id"]]
                if entry["transport_call_sha256"] != r.pilot._transport_hash(call) or entry["request_sha256"] != r.artifacts.digest(request) or intent["request_sha256"] != r.artifacts.digest(request):
                    raise ValueError("Source request/raw/checkpoint identity mismatch")
                if call["messages"] != r._request_messages(request) or call["decoding_contract"]["json_schema"] != r.schema_for(request):
                    raise ValueError("Source prompt/schema mismatch")
                result = classified(request, call, schedule["model"])
                result.update(attempt_number=entry["attempt_number"], attempt_id=entry["attempt_id"], origin="source")
                records[rid].append(result)
            if rid in TARGETS:
                call = raw[old[0]["attempt_id"]]
                group = {"request": request, "schema": call["decoding_contract"]["json_schema"],
                         "options": call["options"], "hf_prompt_tokens": call["hf_prompt_tokens"],
                         "rendered_prompt_sha256": r.artifacts.digest(call["rendered_prompt"]),
                         "token_ids_sha256": r.artifacts.digest(call["hf_prompt_token_ids"])}
                metadata = load(folder / "local_runtime.json")
                group["runtime_binding"] = {key: metadata[key] for key in
                    ("model_digest", "server_version", "profile", "context_tokens", "hf_chat_template_sha256", "sampler_defaults")}
                native = list(folder.glob("strict-nemotron-*.json"))
                if len(native) != 1:
                    raise ValueError("Ambiguous original Nemotron runtime")
                group["native_binding"] = {key: load(native[0])[key] for key in
                    ("model_sha256", "executable_sha256", "context_tokens")}
                check_group(group)
                if len(old) != 2 or first_valid(records[rid]) or schedule["model"] != MODEL:
                    raise ValueError("Target no longer matches the approved failed two-attempt batch")
                for entry in old:
                    evaluate(group, raw[entry["attempt_id"]], entry["attempt_number"])
                groups.append(group)
    invalid = {rid for rid, values in records.items() if not first_valid(values)}
    confidence_items = sum(len(req["item_ids"]) for req in requests.values() if req["kind"] == "confidence")
    actual_costs = costs(raw_calls)
    if invalid != set(TARGETS) or len(requests) != 247 or confidence_items != 322 or actual_costs["physical_inference_dispatches"] != 256:
        raise ValueError("Source denominators/targets differ from the approved run")
    if sum(len(g["request"]["item_ids"]) for g in groups) != 30:
        raise ValueError("Unexpected target item count")
    return {"source": source, "summary": summary, "requests": requests, "records": records,
            "raw_calls": raw_calls, "files": sorted(set(files)), "groups": groups, "actual_costs": actual_costs}


def provenance(data):
    code = Path(__file__).resolve().parent
    return {"variant": VARIANT, "source": str(data["source"]), "model": MODEL,
            "max_total_attempts": MAX_ATTEMPTS, "max_new_calls": 396,
            "targets": list(TARGETS), "groups": data["groups"],
            "source_hashes": {path.relative_to(data["source"]).as_posix(): sha256(path) for path in data["files"]},
            "code_hashes": {path.name: sha256(path) for path in sorted(code.glob("*.py")) if not path.name.startswith("test_")},
            "validator": "legacy reliability_v2.classify plus lossless exact ID reorder; no score selection"}


def prepare(source, output):
    source, output = Path(source).resolve(), Path(output).resolve()
    if source == output or source in output.parents or output in source.parents:
        raise ValueError("Continuation must use a separate, non-overlapping directory")
    data = baseline(source)
    expected = provenance(data)
    if output.exists() and not (output / "provenance.json").exists():
        raise ValueError("Refusing unowned output directory")
    r.immutable(output / "provenance.json", expected)
    return data


def intent_for(group, number):
    request = group["request"]
    return {"request_id": request["request_id"], "attempt_number": number,
            "attempt_id": request["request_id"] + f":attempt:{number}",
            "request_sha256": r.artifacts.digest(request), "schema_sha256": r.artifacts.digest(group["schema"])}


def verify_runtime(runtime, group):
    """Read-only checks BEFORE dispatch; forbid changed templates/options/token IDs."""
    if any(runtime.metadata.get(key) != value for key, value in group["runtime_binding"].items()):
        raise ValueError("Runtime model/profile/version binding changed")
    if not getattr(runtime, "continuation_binding_verified", False):
        actual = runtime.server.preflight()
        if any(actual.get(key) != value for key, value in group["native_binding"].items()):
            raise ValueError("Actual Nemotron binary/model binding changed")
        runtime.continuation_binding_verified = True
    request = group["request"]
    options = generation_options(request["parameters"], runtime.profile["defaults"], runtime.metadata["context_tokens"])
    rendered, count = render_request(runtime.tokenizer, r._request_messages(request), options["num_ctx"], options["num_predict"])
    if options != group["options"] or count != group["hf_prompt_tokens"] or r.artifacts.digest(rendered) != group["rendered_prompt_sha256"]:
        raise ValueError("Runtime request/options/template drift")
    if r.artifacts.digest(runtime.tokenizer.encode(rendered, add_special_tokens=False)) != group["token_ids_sha256"]:
        raise ValueError("Runtime tokenizer drift")


def continue_groups(output, groups, imported, *, max_attempts=MAX_ATTEMPTS, on_checkpoint=None):
    """Separate durable journal. Production cap is fixed by provenance and CLI."""
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    by_id = indexed([dict(g, request_id=g["request"]["request_id"]) for g in groups], "request_id")
    for group in groups:
        check_group(group)
    intents = r.pilot._records(output / "dispatch_intents.jsonl")
    intent_map = indexed(intents, "attempt_id")
    completed = indexed(r.pilot._records(output / "attempts.jsonl"), "attempt_id")
    raw = indexed(r.pilot._records(output / "calls.jsonl"), "request_identity")
    errors = indexed(r.pilot._records(output / "runtime_errors.jsonl"), "attempt_id")
    if set(raw) - set(intent_map) or set(completed) - set(intent_map) or set(errors) - set(intent_map):
        raise ValueError("Orphan raw call or completion")
    histories = {rid: list(imported[rid]) for rid in by_id}
    for intent in intents:
        rid, number = intent["request_id"], intent["attempt_number"]
        group = by_id[rid]
        if intent != intent_for(group, number) or not 3 <= number <= max_attempts:
            raise ValueError("Attempt identity/budget changed")
        history = histories[rid]
        if number != history[-1]["attempt_number"] + 1 or first_valid(history) or not history[-1].get("retry_allowed"):
            raise ValueError("Noncontiguous or unauthorized attempt")
        aid = intent["attempt_id"]
        if aid not in raw:
            if aid not in completed or completed[aid].get("status") != "pre_dispatch_error":
                raise RuntimeError(f"Unknown in-flight outcome: {aid}")
            record = completed[aid]
        else:
            record = evaluate(group, raw[aid], number, errors.get(aid))
            if aid in completed and completed[aid] != record:
                raise ValueError("Completion/raw checkpoint mismatch")
            if aid not in completed:
                r.pilot._append(output / "attempts.jsonl", record)
                completed[aid] = record
        history.append(record)
    runtime = None
    try:
        for rid, group in by_id.items():
            history = histories[rid]
            while not first_valid(history) and history[-1].get("retry_allowed") and history[-1]["attempt_number"] < max_attempts:
                if runtime is None:
                    runtime = LocalOllama(MODEL, output)
                verify_runtime(runtime, group)
                number = history[-1]["attempt_number"] + 1
                intent = intent_for(group, number)
                r.pilot._append(output / "dispatch_intents.jsonl", intent)
                error = None
                try:
                    runtime.generate(r._request_messages(group["request"]), group["request"]["parameters"],
                                     json_schema=group["schema"], request_identity=intent["attempt_id"])
                except Exception as exc:
                    error = exc
                    error_record = {"attempt_id": intent["attempt_id"], "type": type(exc).__name__, "message": str(exc)}
                    r.pilot._append(output / "runtime_errors.jsonl", error_record)
                    errors[intent["attempt_id"]] = error_record
                calls = indexed(r.pilot._records(output / "calls.jsonl"), "request_identity")
                call = calls.get(intent["attempt_id"])
                if call is None:
                    # Do not infer that a network send did not happen. Unresolved intent halts resume.
                    raise RuntimeError("Unknown in-flight outcome after runtime failure") from error
                record = evaluate(group, call, number, errors.get(intent["attempt_id"]))
                r.pilot._append(output / "attempts.jsonl", record)
                completed[intent["attempt_id"]] = record
                history.append(record)
                if on_checkpoint is not None:
                    on_checkpoint()
    finally:
        if runtime is not None:
            runtime.close()
    return list(completed.values())


def summary(data, output, state, active_seconds=0, error=None):
    records = r.pilot._records(output / "attempts.jsonl")
    calls = r.pilot._records(output / "calls.jsonl")
    combined = {rid: values + [x for x in records if x["request_id"] == rid]
                for rid, values in data["records"].items()}
    raw = data["raw_calls"] + calls
    caps = []
    for cap in CAPS:
        selected = {rid: first_valid(values, cap) for rid, values in combined.items()}
        retained = []
        for call in raw:
            rid, number = call["request_identity"].rsplit(":attempt:", 1)
            found = selected[rid]
            if int(number) <= cap and (found is None or int(number) <= found["attempt_number"]):
                retained.append(call)
        caps.append({"max_total_attempts": cap, "valid_logical_requests": sum(x is not None for x in selected.values()),
                     "logical_request_denominator": 247,
                     "valid_confidence_values": sum(len(data["requests"][rid]["item_ids"]) for rid, found in selected.items()
                                                    if found and data["requests"][rid]["kind"] == "confidence"),
                     "confidence_value_denominator": 322,
                     "unresolved_requests_with_unobserved_budget": sum(found is None and combined[rid][-1]["attempt_number"] < cap
                                                                       for rid, found in selected.items()),
                     "hypothetical_first_valid_prefix_costs": costs(retained),
                     "coverage_is_observed_not_guaranteed": True})
    groups = []
    for rid in TARGETS:
        history = combined[rid]
        valid = first_valid(history)
        groups.append({"request_id": rid, "item_count": len(data["requests"][rid]["item_ids"]),
                       "first_valid_attempt": valid["attempt_number"] if valid else None,
                       "max_observed_attempt": max(x["attempt_number"] for x in history),
                       "final_status": "valid" if valid else history[-1]["status"],
                       "selected_result": valid, "attempts": history})
    value = {"variant": VARIANT, "status": state, "max_total_attempts": MAX_ATTEMPTS,
             "max_additional_attempts_from_original_first": 100, "max_new_calls_after_two_saved_attempts": 396,
             "original_logical_requests": 247, "confidence_value_denominator": 322,
             "target_group_count": 4, "target_value_count": 30,
             "original_actual_costs": data["actual_costs"], "new_actual_costs": costs(calls),
             "original_actual_technical_retries": 9,
             "new_failed_attempts": sum(x["status"] != "valid" for x in records),
             "historical_failed_attempts_under_frozen_validator": sum(x["status"] != "valid" for values in data["records"].values() for x in values),
             "remaining_invalid_groups": sum(g["first_valid_attempt"] is None for g in groups),
             "original_run_active_seconds": data["summary"]["active_seconds"],
             "continuation_active_seconds": active_seconds, "caps": caps, "groups": groups,
             "max_observed_attempt": max(g["max_observed_attempt"] for g in groups),
             "all_confidence_values_valid": caps[-1]["valid_confidence_values"] == 322,
             "provenance_sha256": sha256(output / "provenance.json")}
    if error:
        value["error"] = error
    write_json(output / "retry_summary.json", value)
    return value


@contextmanager
def execution_lock(output):
    path = output / "execution.lock"
    with path.open("x", encoding="utf-8") as stream:
        stream.write(str(os.getpid()))
        stream.flush()
        os.fsync(stream.fileno())
    try:
        yield
    finally:
        path.unlink()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--prepare-only", action="store_true")
    mode.add_argument("--run", action="store_true")
    args = parser.parse_args(argv)
    output = args.output.resolve()
    data = prepare(args.source, output)
    with execution_lock(output):
        return execute_mode(args, data, output)


def execute_mode(args, data, output):
    prior = load(output / "retry_summary.json") if (output / "retry_summary.json").exists() else {}
    if args.prepare_only:
        summary(data, output, "prepared", prior.get("continuation_active_seconds", 0))
        return 0
    start = time.perf_counter()
    state, error = "finished", None
    try:
        # Pin installed executable/GGUF/CUDA files against the ORIGINAL run, without model inference.
        for path in data["files"]:
            if (path.parent.name == "confidence_nemotron" and path.name.startswith("strict-nemotron-")
                    and path.suffix == ".json"):
                metadata = load(path)
                for name in ("executable", "model", "cuda_backend"):
                    file_key = "model_path" if name == "model" else name
                    if sha256(Path(metadata[file_key])) != metadata[name + "_sha256"]:
                        raise ValueError(f"Original backend {name} changed")
        def checkpoint():
            summary(data, output, "running", prior.get("continuation_active_seconds", 0) + time.perf_counter() - start)
        checkpoint()
        continue_groups(output, data["groups"], data["records"], on_checkpoint=checkpoint)
        r.immutable(output / "provenance.json", provenance(data))
    except BaseException as exc:
        state, error = "halted", {"type": type(exc).__name__, "message": str(exc)}
        raise
    finally:
        result = summary(data, output, state, prior.get("continuation_active_seconds", 0) + time.perf_counter() - start, error)
    return 0 if result["all_confidence_values_valid"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
