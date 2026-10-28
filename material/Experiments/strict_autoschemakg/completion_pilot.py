"""Optional, isolated four-arm construction runner. Evaluation is a separate stage.

All stochastic work belongs to reliability_v2.requests. This module freezes its
inputs and budgets, composes shared results, and never interprets quality as a
reason to redraw. The default CLI is strictly read-only.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path

from . import completion_contracts as c, temporal_compiler as compiler
from . import temporal_reasoner as reasoner, reliability_v2 as r
from . import local_runtime, retry_continuation, recall_pilot, technical_repairs
from .contract import sha256

VARIANT = "local_lamport_completion_reasoning_v1"
ARMS = ("baseline", "completion", "reasoning", "completion_reasoning")
PAUSED = ["mcq", "schema", "multi_hop"]
COMPILER_PROTOCOL = "temporal_compilation_v1"


def _read(path):
    from . import immutable_publish
    return immutable_publish.read_json(path)


def _same(path, value):
    from . import immutable_publish
    if path.exists() and not immutable_publish.equal_json(_read(path), value):
        raise ValueError(f"Frozen contract changed: {path}")


def _compiler_requests(items, index, prefix):
    requests = compiler.formalization_requests(items, index)
    for request in requests:
        request["request_id"] = prefix + ":" + request["request_id"]
    return requests


def _stage_contract(schedule, protocol, schema_fn, *, variant=VARIANT, model=None,
                    context=local_runtime.CONTEXT):
    model = r.pilot.CONSTRUCTOR if model is None else model
    local_runtime.validate_context(context, model)
    contract = {"model": model, "variant": variant,
                "retry_policy": r.technical_retry_policy(), "protocol_id": protocol,
                "requests": schedule}
    if context != local_runtime.CONTEXT:
        contract["context_tokens"] = context
    budget = {
                "request_hash": r.artifacts.digest(schedule),
                "schemas": {q["request_id"]: schema_fn(q) for q in schedule},
                "logical_requests": len(schedule),
                "max_total_attempts_per_request": r.MAX_TOTAL_ATTEMPTS,
                "max_physical_calls": len(schedule) * r.MAX_TOTAL_ATTEMPTS,
                "max_input_plus_output_tokens": len(schedule) * r.MAX_TOTAL_ATTEMPTS * context,
                "max_output_tokens": sum(
                    (q["adaptive_output_ceiling"] if q.get("adaptive_output_protocol") ==
                     technical_repairs.ADAPTIVE_PROTOCOL_V2
                     else technical_repairs.MAX_ADAPTIVE_OUTPUT if q.get("adaptive_output_protocol") ==
                     technical_repairs.ADAPTIVE_PROTOCOL
                     else q["parameters"]["max_new_tokens"]) for q in schedule) * r.MAX_TOTAL_ATTEMPTS,
                "context_tokens": context,
                "bound_policy": "conservative_context_ceiling_not_token_estimate",
                "admission": "pinned_tokenizer_full_chat_template_plus_output_reserve_no_truncation"}
    if any(q.get("adaptive_output_protocol") == technical_repairs.ADAPTIVE_PROTOCOL_V2 for q in schedule):
        budget.update(safety_tokens_per_call=technical_repairs.OUTPUT_SAFETY_TOKENS,
                      max_http_timeout_seconds_per_call=1200,
                      max_http_timeout_seconds=budget["max_physical_calls"] * 1200,
                      admission="pinned_tokenizer_full_chat_template_plus_output_plus_256_no_truncation")
    return contract, budget


def preflight(output: Path) -> dict:
    """Read source/code/profile contracts only. No directories, tokenizer or HTTP."""
    inputs = c.load_inputs()
    schedules = {"construction/completion": c.completion_requests(inputs),
                 "compilation/baseline": _compiler_requests(inputs["items"], inputs["event_index"], "baseline")}
    modules = (c, compiler, reasoner, r, local_runtime, retry_continuation,
               r.pilot, r.artifacts, recall_pilot)
    files = {Path(module.__file__).resolve() for module in modules}
    files.add(Path(__file__).resolve())
    # Includes tokenizer/transport and native helper implementations, not just
    # the prompt entrypoints. A code change requires a separate run directory.
    folder = Path(__file__).parent
    for name in ("contract.py", "recall_methods.py", "retry_policy.py", "nemotron_server.py", "completion_measurements.py"):
        files.add(folder / name)
    return {"variant": VARIANT, "output": str(Path(output).resolve()), "arm_order": list(ARMS),
            "input_hashes": inputs["input_hashes"], "baseline_counts": inputs["baseline_counts"],
            "code_hashes": {str(path.relative_to(c.ROOT)): sha256(path) for path in sorted(files)},
            "profiles": deepcopy(r.PROFILES), "rule_version": reasoner.RULE_VERSION,
            "completion_protocol": c.PROTOCOL_ID, "compiler_protocol": COMPILER_PROTOCOL,
            "retry_policy": r.technical_retry_policy(), "context_tokens": local_runtime.CONTEXT,
            "prompt_hashes": {key: r.artifacts.digest(value) for key, value in schedules.items()},
            "paused_stages": PAUSED, "evaluation": "separate_not_dispatched",
            "shared_baseline": "byte_identical_saved_extraction_no_new_baseline_calls"}


def _audit_stage(path, schedule, protocol, schema_fn, classifier, *, variant=VARIANT, model=None,
                 context=local_runtime.CONTEXT):
    model = r.pilot.CONSTRUCTOR if model is None else model
    contract, budget = _stage_contract(schedule, protocol, schema_fn, variant=variant, model=model,
                                       context=context)
    _same(path / "schedule.json", contract)
    _same(path / "budget.json", budget)
    if path.exists():
        audit_kwargs = {"context": context} if context != local_runtime.CONTEXT else {}
        intents, recorded, raw = r.audit_existing(path, schedule, model, classifier_fn=classifier,
                                                  **audit_kwargs)
        for intent in intents:
            if intent["attempt_id"] not in recorded and intent["attempt_id"] not in raw:
                raise RuntimeError("Unknown in-flight outcome, refusing automatic redraw: " + intent["attempt_id"])
        if intents and (not (path / "schedule.json").is_file() or not (path / "budget.json").is_file()):
            raise ValueError("Dispatched stage lacks frozen schedule or budget")


def _stage(path, schedule, protocol, schema_fn, classifier, *, variant=VARIANT, model=None,
           context=local_runtime.CONTEXT):
    model = r.pilot.CONSTRUCTOR if model is None else model
    context_kwargs = {"context": context} if context != local_runtime.CONTEXT else {}
    _audit_stage(path, schedule, protocol, schema_fn, classifier, variant=variant, model=model,
                 **context_kwargs)
    contract, budget = _stage_contract(schedule, protocol, schema_fn, variant=variant, model=model,
                                       **context_kwargs)
    r.immutable(path / "schedule.json", contract)
    r.immutable(path / "budget.json", budget)
    return r.requests(path, schedule, model, variant=variant,
                      schema_fn=schema_fn, classifier_fn=classifier, protocol_id=protocol,
                      **context_kwargs)


def _additions(inputs, bound):
    seen = {(item["category"], r.artifacts.digest(item["value"])) for item in inputs["items"]}
    added = []
    for candidate in bound["candidates"]:
        key = candidate["category"], r.artifacts.digest(candidate["value"])
        if key not in seen:
            added.append({"id": candidate["id"], "category": candidate["category"],
                          "value": deepcopy(candidate["value"]), "origin_item_id": candidate["id"]})
            seen.add(key)
    # Never re-index B. New endpoints remain conservative separate occurrences,
    # with ambiguity checked across B+C without changing frozen B endpoint IDs.
    all_index = c._endpoints(inputs["items"] + added, c.SOURCE_ID)
    new_ids = {x["id"] for x in added}
    index = deepcopy(inputs["event_index"])
    index.update({key: value for key, value in all_index.items() if value["origin_item_id"] in new_ids})
    return added, index


def _bytes(path, content):
    from . import immutable_publish
    if immutable_publish.enabled():
        return immutable_publish.publish_bytes(path, content)
    if path.exists():
        if path.read_bytes() != content:
            raise ValueError(f"Frozen native input changed: {path}")
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("xb") as stream:
            stream.write(content)


def _status(*statuses):
    return "missing" if "missing" in statuses else "partial" if "partial" in statuses else "complete"


def _reason(path, primitives):
    """Save measured duration once; resume never substitutes a recomputed timing."""
    r.immutable(path / "primitives.json", primitives)
    target = path / "result.json"
    if target.exists():
        result = _read(target)
        expected = reasoner.materialize(primitives)
        if {k: v for k, v in result.items() if k != "elapsed_seconds"} != {
                k: v for k, v in expected.items() if k != "elapsed_seconds"}:
            raise ValueError("Frozen reasoning result changed")
        return result
    result = reasoner.materialize(primitives)
    r.immutable(target, result)
    return result


def _producers(schedule, results, *, candidates=None):
    by_id = {row["request_id"]: row for row in results}
    requests = {row["request_id"]: row for row in schedule}
    decisions = ([(x["id"], x["request_id"], "completion", x["id"]) for x in candidates]
                 if candidates is not None else
                 [("formalization:" + item, req["request_id"], "formalization", item)
                  for req in schedule for item in req["item_ids"]])
    return {decision: {"decision_id": decision, "kind": kind, "item_id": item,
                       "request_id": request_id, "request": requests[request_id], "result": by_id[request_id]}
            for decision, request_id, kind, item in decisions}


def execute(output: Path, *, resume: bool = False) -> dict:
    output = Path(output).resolve()
    manifest = preflight(output)
    inputs = c.load_inputs()
    completion = c.completion_requests(inputs)
    baseline = _compiler_requests(inputs["items"], inputs["event_index"], "baseline")
    construction = output / "construction/completion"
    base_path = output / "compilation/baseline"
    new_path = output / "compilation/additions"
    if output.exists():
        if not resume or not (output / "input_manifest.json").is_file():
            raise ValueError("Existing output requires --resume and a frozen input manifest")
        _same(output / "input_manifest.json", manifest)
        # Read-only audit of EVERY saved request contract precedes the lock and
        # all writes, including requests in a later, dynamically created stage.
        _audit_stage(construction, completion, c.PROTOCOL_ID, c.schema_for, c.classify)
        _audit_stage(base_path, baseline, COMPILER_PROTOCOL, compiler.schema_for, compiler.classify)
        if new_path.exists():
            finals = construction / "final_responses.json"
            if not finals.is_file():
                raise ValueError("Addition compiler exists without completion checkpoint")
            bound = c.bind_candidates(inputs, completion, _read(finals))
            added, index = _additions(inputs, bound)
            new = _compiler_requests(added, index, "additions")
            _audit_stage(new_path, new, COMPILER_PROTOCOL, compiler.schema_for, compiler.classify)
    else:
        if resume:
            raise ValueError("Cannot resume missing output")
        output.mkdir(parents=True)
    with retry_continuation.execution_lock(output):
        r.immutable(output / "input_manifest.json", manifest)
        completed = _stage(construction, completion, c.PROTOCOL_ID, c.schema_for, c.classify)
        bound = c.bind_candidates(inputs, completion, completed)
        r.immutable(output / "construction/bound_candidates.json", bound)
        added, combined_index = _additions(inputs, bound)
        for name, items, index in (("baseline", inputs["items"], inputs["event_index"]),
                                   ("combined", inputs["items"] + added, combined_index)):
            r.immutable(output / "compilation" / name / "items.json", items)
            r.immutable(output / "compilation" / name / "event_index.json", index)
        base_results = _stage(base_path, baseline, COMPILER_PROTOCOL, compiler.schema_for, compiler.classify)
        base_projection = compiler.project_primitives(baseline, base_results, inputs["event_index"])
        r.immutable(base_path / "projection.json", base_projection)
        new = _compiler_requests(added, combined_index, "additions")
        new_results = _stage(new_path, new, COMPILER_PROTOCOL, compiler.schema_for, compiler.classify)
        new_projection = compiler.project_primitives(new, new_results, combined_index)
        r.immutable(new_path / "projection.json", new_projection)
        base_reasoning = _reason(output / "reasoning/baseline", base_projection["primitives"])
        combined_reasoning = _reason(output / "reasoning/combined", base_projection["primitives"] + new_projection["primitives"])
        original = c.BASELINE.read_bytes()
        combined = (original if bound["native_row"] == inputs["baseline"] else
                    (json.dumps(bound["native_row"], ensure_ascii=False, allow_nan=False) + "\n").encode("utf-8"))
        statuses = {"baseline": "complete", "completion": bound["dependency_status"],
                    "reasoning": base_projection["dependency_status"],
                    "completion_reasoning": _status(bound["dependency_status"], base_projection["dependency_status"],
                                                    new_projection["dependency_status"])}
        arm_inputs = {}
        for arm in ARMS:
            content = combined if arm in ("completion", "completion_reasoning") else original
            derived = (base_reasoning["derived"] if arm == "reasoning" else
                       combined_reasoning["derived"] if arm == "completion_reasoning" else [])
            candidates = bound["candidates"] if arm in ("completion", "completion_reasoning") else []
            native_path = output / "arms" / arm / "extraction.jsonl"
            _bytes(native_path, content)
            arm_inputs[arm] = {"native_input_hash": hashlib.sha256(content).hexdigest(),
                              "native_input_path": str(native_path.relative_to(output)).replace("\\", "/"),
                              "candidate_ids": [x["id"] for x in candidates],
                              "derived_ids": [x["id"] for x in derived], "dependency_status": statuses[arm]}
            r.immutable(output / "arms" / arm / "input.json", arm_inputs[arm])
        producers = {**_producers(completion, completed, candidates=bound["candidates"]),
                     **_producers(baseline, base_results), **_producers(new, new_results)}
        r.immutable(output / "arm_inputs.json", arm_inputs)
        r.immutable(output / "producers.json", producers)
        r.immutable(output / "evaluation/status.json", {"status": "not_started", "paused_stages": PAUSED})
        stages = {"completion": (construction, completed), "baseline_compiler": (base_path, base_results),
                  "addition_compiler": (new_path, new_results)}
        summary = {"variant": VARIANT, "status": _status(*statuses.values()), "arm_inputs": arm_inputs,
                   "producers": producers, "paused_stages": PAUSED,
                   "evaluation": "not_started", "stage_costs": {
                       name: {"logical_requests": len(results), "actual_attempts": sum(x["attempt_count"] for x in results),
                              "retry_budget_exhausted": sum(x["retry_budget_exhausted"] for x in results),
                              "costs": recall_pilot.costs(r.pilot._records(path / "calls.jsonl"))}
                       for name, (path, results) in stages.items()},
                   "reasoner_seconds": {"baseline": base_reasoning["elapsed_seconds"],
                                        "combined": combined_reasoning["elapsed_seconds"]},
                   "baseline_costs": "historical_reused_not_charged", "shared_costs": "each_physical_stage_counted_once"}
        r.immutable(output / "technical_summary.json", summary)
        from . import completion_measurements
        completion_measurements._evaluate_locked(output, arm_inputs, producers)
        return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args(argv)
    result = execute(args.output, resume=args.resume) if args.execute else preflight(args.output)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
