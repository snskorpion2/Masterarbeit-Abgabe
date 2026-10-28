"""Bounded, isolated Lamport compiler and completion probes.

The default invocation only inspects frozen inputs and code. Model execution
uses the existing reliability stage and never retries an unwanted answer.
"""
from __future__ import annotations

import argparse
from collections import Counter
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import random

from . import completion_contracts as c, completion_measurements as m
from . import completion_pilot as p, temporal_compiler as compiler
from . import temporal_reasoner as reasoner, reliability_v2 as r
from . import local_runtime, retry_continuation, recall_pilot
from .contract import sha256

SEED = 28092026
VARIANTS = {"compiler": "local_lamport_temporal_compiler_v2",
            "completion": "local_lamport_completion_pair_scan_v2"}
PROTOCOLS = {"compiler": "temporal_compilation_v2",
             "completion": "source_grounded_completion_pair_scan_v2"}
PAUSED = ["mcq", "schema", "multi_hop", "native_judge", "llm_repair"]
SEARCH_PARAGRAPH = (
    "\nPAIR AND SUBGRAPH SEARCH: For every existing node, inspect its incident "
    "statements and their source evidence. Search the complete source for missing "
    "connections between existing nodes, and for additional relations between "
    "pairs that are already connected. New source-grounded nodes outside the "
    "existing node set are allowed. Return only additional candidates in the "
    "requested category. An empty candidates list is valid."
)


def _read(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _plan(mode: str, inputs: dict) -> list[dict]:
    if mode == "compiler":
        schedule = compiler.formalization_requests(inputs["items"], inputs["event_index"],
                                                   contract_version="v2")
        for request in schedule:
            request["request_id"] = "compiler-v2:" + request["request_id"]
        return schedule
    controls = c.completion_requests(inputs)
    rng = random.Random(SEED)
    plan = []
    for control in controls:
        pair = deepcopy(control)
        pair["request_id"] = control["request_id"] + ":pair_scan_v2"
        pair["prompt"] += SEARCH_PARAGRAPH
        block = [control, pair]
        rng.shuffle(block)
        plan.extend(block)
    return plan


def _code_hashes() -> dict:
    modules = (c, m, p, compiler, reasoner, r, local_runtime, retry_continuation,
               recall_pilot, r.pilot, r.artifacts)
    paths = {Path(module.__file__).resolve() for module in modules}
    paths.add(Path(__file__).resolve())
    folder = Path(__file__).parent
    for name in ("contract.py", "recall_methods.py", "retry_policy.py", "nemotron_server.py"):
        paths.add(folder / name)
    return {str(path.relative_to(c.ROOT)).replace("\\", "/"): sha256(path)
            for path in sorted(paths)}


def preflight(output: Path, mode: str) -> dict:
    """Return the full frozen manifest without writing or initializing a model."""
    if mode not in VARIANTS:
        raise ValueError("Unknown probe mode")
    inputs = c.load_inputs()
    schedule = _plan(mode, inputs)
    if len(schedule) != 6:
        raise ValueError("Expected exactly six probe requests")
    return {"schema_version": 1, "mode": mode, "variant": VARIANTS[mode],
            "output": str(Path(output).resolve()), "seed": SEED,
            "input_hashes": inputs["input_hashes"],
            "baseline_counts": inputs["baseline_counts"],
            "code_hashes": _code_hashes(), "profiles": deepcopy(r.PROFILES),
            "model": r.pilot.CONSTRUCTOR, "protocol_id": PROTOCOLS[mode],
            "request_hash": r.artifacts.digest(schedule),
            "prompt_hashes": {q["request_id"]: hashlib.sha256(q["prompt"].encode("utf-8")).hexdigest()
                              for q in schedule},
            "retry_policy": r.technical_retry_policy(),
            "max_total_attempts": r.MAX_TOTAL_ATTEMPTS,
            "paused_stages": PAUSED}


def _stage_spec(mode):
    return ((compiler.schema_for, compiler.classify) if mode == "compiler"
            else (c.schema_for, c.classify))


def _audit(output, mode, manifest, schedule):
    p._same(output / "input_manifest.json", manifest)
    p._same(output / "plan.json", schedule)
    if not (output / "input_manifest.json").is_file() or not (output / "plan.json").is_file():
        raise ValueError("Existing output lacks frozen manifest or plan")
    schema, classifier = _stage_spec(mode)
    p._audit_stage(output / "construction", schedule, PROTOCOLS[mode], schema,
                   classifier, variant=VARIANTS[mode])
    confidence_path = output / "producer_confidence"
    finals = output / "construction/final_responses.json"
    if (output / "summary.json").exists() and (
            not finals.is_file() or not (confidence_path / "final_responses.json").is_file()):
        raise ValueError("Summary lacks final stage checkpoints")
    if finals.is_file():
        results = _read(finals)
        if mode == "compiler":
            inputs = c.load_inputs()
            for name, repair in (("strict", False), ("repaired", True)):
                projection = compiler.project_primitives(schedule, results, inputs["event_index"],
                                                         repair_spans=repair)
                p._same(output / f"projection_{name}.json", projection)
                reasoning = output / "reasoning" / name / "result.json"
                if reasoning.is_file():
                    expected = reasoner.materialize(projection["primitives"])
                    observed = _read(reasoning)
                    if {k: v for k, v in observed.items() if k != "elapsed_seconds"} != {
                            k: v for k, v in expected.items() if k != "elapsed_seconds"}:
                        raise ValueError("Frozen reasoning result changed")
                    p._same(output / "reasoning" / name / "proofs.json",
                            _proofs(projection["primitives"], observed["derived"]))
        else:
            inputs = c.load_inputs()
            by_id = {x["request_id"]: x for x in results}
            for name, selected in (("control", False), ("pair_scan", True)):
                subset = [q for q in schedule if q["request_id"].endswith(":pair_scan_v2") == selected]
                bound = c.bind_candidates(inputs, subset, [by_id[q["request_id"]] for q in subset])
                p._same(output / "arms" / name / "bound_candidates.json", bound)
                native = output / "arms" / name / "extraction.jsonl"
                expected = (json.dumps(bound["native_row"], ensure_ascii=False, allow_nan=False) + "\n").encode("utf-8")
                if native.exists() and native.read_bytes() != expected:
                    raise ValueError("Frozen native union changed")
    if confidence_path.exists():
        if not finals.is_file():
            raise ValueError("Confidence stage lacks final construction checkpoint")
        producers = _producers(mode, schedule, _read(finals), output)
        confidence = m._producer_confidence(producers)
        p._audit_stage(confidence_path, confidence, m.PROTOCOL, r.schema_for,
                       r.classify, variant=VARIANTS[mode])


def _producers(mode, schedule, results, output):
    if mode == "compiler":
        return p._producers(schedule, results)
    inputs = c.load_inputs()
    controls = [q for q in schedule if not q["request_id"].endswith(":pair_scan_v2")]
    pairs = [q for q in schedule if q["request_id"].endswith(":pair_scan_v2")]
    by_id = {x["request_id"]: x for x in results}
    producers = {}
    for arm, subset in (("control", controls), ("pair_scan", pairs)):
        bound_path = output / "arms" / arm / "bound_candidates.json"
        bound = _read(bound_path) if bound_path.exists() else c.bind_candidates(
            inputs, subset, [by_id[q["request_id"]] for q in subset])
        producers.update(p._producers(subset, results, candidates=bound["candidates"]))
    return producers


def _proofs(primitives, derived):
    return {row["id"]: {"valid": reasoner.verify_proof(row, primitives, derived),
                        "premise_ids": row["premise_ids"], "rule_id": row["rule_id"]}
            for row in derived}


def _compiler_outputs(output, inputs, schedule, results, *, deterministic_repairs=False):
    projections = {}
    for name, repair in (("strict", False), ("repaired", True)):
        projection = compiler.project_primitives(schedule, results, inputs["event_index"],
                                                 repair_spans=repair, deterministic_repairs=deterministic_repairs)
        r.immutable(output / f"projection_{name}.json", projection)
        reasoning = p._reason(output / "reasoning" / name, projection["primitives"])
        r.immutable(output / "reasoning" / name / "proofs.json",
                    _proofs(projection["primitives"], reasoning["derived"]))
        projections[name] = {"accepted_atoms": len(projection["primitives"]),
                             "rejected_atoms": len(projection["invalid_bindings"]),
                             "unformalized_items": len({x["item_id"] for x in projection["unformalized"]}),
                             "offset_repairs": len(projection.get("span_repairs", [])),
                             "derived_edges": len(reasoning["derived"]),
                             "conflicts": len(reasoning["conflicts"]),
                             "invalid_proofs": sum(not x["valid"] for x in
                                                   _proofs(projection["primitives"], reasoning["derived"]).values()),
                             "dependency_status": projection["dependency_status"]}
    return projections


def _completion_outputs(output, inputs, schedule, results):
    by_id = {x["request_id"]: x for x in results}
    arms, keys = {}, {}
    for name, selected in (("control", False), ("pair_scan", True)):
        subset = [q for q in schedule if q["request_id"].endswith(":pair_scan_v2") == selected]
        bound = c.bind_candidates(inputs, subset, [by_id[q["request_id"]] for q in subset])
        r.immutable(output / "arms" / name / "bound_candidates.json", bound)
        native = (json.dumps(bound["native_row"], ensure_ascii=False, allow_nan=False) + "\n").encode("utf-8")
        p._bytes(output / "arms" / name / "extraction.jsonl", native)
        keys[name] = {(x["category"], r.artifacts.digest(x["value"])) for x in bound["candidates"]}
        arms[name] = {"candidates": len(bound["candidates"]),
                      "bound": sum(x["status"] == "bound" for x in bound["bindings"]),
                      "binding_findings": dict(Counter(f for x in bound["bindings"] for f in x["findings"])),
                      "native_counts": {category: len(bound["native_row"][field])
                                        for category, field in c.CATEGORIES.items()},
                      "missing_responses": sum(by_id[q["request_id"]]["status"] != "valid" for q in subset),
                      "dependency_status": bound["dependency_status"]}
    overlap = len(keys["control"] & keys["pair_scan"])
    arms["control"]["overlap_exact_category_value"] = overlap
    arms["pair_scan"]["overlap_exact_category_value"] = overlap
    return arms


def _cost_stage(path, results):
    calls = r.pilot._records(path / "calls.jsonl")
    ids = [x["request_identity"] for x in calls]
    if len(ids) != len(set(ids)):
        raise ValueError("Duplicate physical dispatch identity")
    return {"logical_requests": len(results),
            "physical_attempts": len(calls),
            "retry_distribution": {str(key): count for key, count in Counter(
                x["attempt_count"] for x in results).items()},
            "retry_budget_exhausted": sum(x["retry_budget_exhausted"] for x in results),
            "costs": m._costs(calls)}


def _valid_confidence_values(results):
    return sum(len(row["parsed"]["judgments"]) for row in results if row["status"] == "valid")


def execute(output: Path, mode: str, *, resume: bool = False) -> dict:
    output = Path(output).resolve()
    manifest = preflight(output, mode)
    inputs = c.load_inputs()
    schedule = _plan(mode, inputs)
    if output.exists():
        if not resume:
            raise ValueError("Existing output requires --resume")
        _audit(output, mode, manifest, schedule)
    elif resume:
        raise ValueError("Cannot resume missing output")
    else:
        output.mkdir(parents=True)
    schema, classifier = _stage_spec(mode)
    with retry_continuation.execution_lock(output):
        r.immutable(output / "input_manifest.json", manifest)
        r.immutable(output / "plan.json", schedule)
        results = p._stage(output / "construction", schedule, PROTOCOLS[mode], schema,
                           classifier, variant=VARIANTS[mode])
        details = (_compiler_outputs(output, inputs, schedule, results) if mode == "compiler"
                   else _completion_outputs(output, inputs, schedule, results))
        producers = _producers(mode, schedule, results, output)
        expected = 47 if mode == "compiler" else sum(x["candidates"] for x in details.values())
        if len(producers) != expected:
            raise ValueError("Producer decisions do not match output cardinality")
        confidence_schedule = m._producer_confidence(producers)
        confidence = p._stage(output / "producer_confidence", confidence_schedule,
                              m.PROTOCOL, r.schema_for, r.classify, variant=VARIANTS[mode])
        confidence_values = _valid_confidence_values(confidence)
        summary = {"schema_version": 1, "mode": mode, "variant": VARIANTS[mode],
                   "status": "complete" if all(x["status"] == "valid" for x in results + confidence) else "partial",
                   "input_hashes": inputs["input_hashes"], "baseline_counts": inputs["baseline_counts"],
                   mode: details,
                   "confidence": {"expected_decisions": len(producers),
                                  "valid_decisions": confidence_values,
                                  "logical_requests": len(confidence_schedule)},
                   "stage_costs": {"construction": _cost_stage(output / "construction", results),
                                   "producer_confidence": _cost_stage(output / "producer_confidence", confidence)},
                   "historical_baseline": "reused_not_charged", "paused_stages": PAUSED}
        r.immutable(output / "summary.json", summary)
        return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=tuple(VARIANTS), required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args(argv)
    if args.resume and not args.execute:
        parser.error("--resume requires --execute")
    result = execute(args.output, args.mode, resume=args.resume) if args.execute else preflight(args.output, args.mode)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
