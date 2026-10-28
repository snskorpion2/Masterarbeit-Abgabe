"""Isolated, capped source-grounding pilot. Default is read-only preflight.

Run separate method arms from an immutable saved graph. Never rewrite older
experiments, never retry valid empty semantic outcomes. No MCQ/schema/confidence.
The v1 entry points are historical. New execution requires the explicit v2
entry point because EV merging and anchor search have changed.
"""
from __future__ import annotations

import argparse
import ast
from collections import Counter
from copy import deepcopy
import json
from pathlib import Path
import re

from . import grounded_evidence_v1 as e, grounded_supplement_v2 as s
from . import supplement_diagnostics_v1 as old, completion_contracts as c
from . import completion_pilot as p, completion_probe as probe, completion_measurements as m
from . import reliability_v2 as r, technical_repairs, immutable_publish, retry_continuation
from .contract import sha256

VARIANT = "grounded_methods_pilot_v1"
ACTIVE_VARIANT = "grounded_methods_pilot_v2_occurrence_preserving_bounded_search"
CONTEXT = 131072
MAX_REQUESTS = 180


def code_files():
    pending, found = [Path(__file__).resolve()], set()
    # Explicit opt-in modules are also frozen before any dispatch.
    pending += [x for x in Path(__file__).parent.glob("grounded_*.py")]
    pending += [x for x in Path(__file__).parent.glob("compiler_grounded_v3.py")]
    while pending:
        file = pending.pop()
        if file in found:
            continue
        found.add(file)
        for node in ast.walk(ast.parse(file.read_text(encoding="utf-8-sig"))):
            if isinstance(node, ast.ImportFrom) and node.level == 1:
                names = [node.module.split(".")[0]] if node.module else [x.name for x in node.names]
                pending += [file.parent / (name + ".py") for name in names if (file.parent / (name + ".py")).is_file()]
    found.add(r.DEFAULT_SOURCE / "atlas_rag/llm_generator/prompt/triple_extraction_prompt.py")
    found.add(r.DEFAULT_SOURCE / "EvaluateKGC/TripleAccuracy/triple_acc.py")
    return found


def preflight(source, baseline, base_stage, output, *, methods=("A", "A_chunk", "B", "K", "R")):
    raise ValueError("grounded_methods_pilot_v1 is historical; use the explicit grounded_methods_pilot_v2 contract")


def _active_preflight(source, baseline, base_stage, output, *, methods=("A", "A_chunk", "B", "K", "R")):
    old._protect_output(output, source, baseline, base_stage)
    if not set(methods) <= {"A", "A_chunk", "B", "K", "R"} or not methods or len(set(methods)) != len(methods):
        raise ValueError("Unknown or duplicate methods")
    inputs, history = old.load_inputs(source, baseline, base_stage)
    return {"variant": ACTIVE_VARIANT, "methods": list(methods), "source": str(Path(source).resolve()),
            "baseline": str(Path(baseline).resolve()), "base_stage": str(Path(base_stage).resolve()),
            "input_hashes": inputs["input_hashes"], "history_hashes": history["hashes"],
            "code_hashes": {str(x.relative_to(c.ROOT)).replace("\\", "/"): sha256(x) for x in sorted(code_files())},
            "context": CONTEXT, "output_ceiling": 16384, "max_logical_requests": MAX_REQUESTS,
            "max_physical_calls": MAX_REQUESTS * r.MAX_TOTAL_ATTEMPTS,
            "glean_rounds": 3, "chunks": 2, "completion_max_nodes_per_category": 2,
            "compiler_batch_events": 12, "verification_batch": 12,
            "semantic_dedup_max_pairs": 24, "semantic_dedup_policy": "candidate_similarity_then_independent_equivalence",
            "event_merge_protocol": "occurrence_preserving_v2",
            "anchor_supplement_policy": "all_restored_anchors_single_pass",
            "anchor_supplement_passes": 1, "fact_completeness_claim": False,
            "claim": "single_article_method_diagnosis_not_causal_effect_or_gold",
            "paused": ["mcq", "schema", "confidence", "full_factorial", "scaling"],
            "baseline_counts": inputs["baseline_counts"]}


class Engine:
    def __init__(self, output):
        self.output = Path(output)
        self.stages = []

    def call(self, query, *, judge=False, schema=e.schema_for, classifier=e.classify):
        if len(self.stages) >= MAX_REQUESTS:
            raise RuntimeError("Declared logical request cap reached; preserve checkpoint")
        query = technical_repairs.enable_adaptive_output_v2([query], ceiling=16384)[0]
        name = re.sub(r"[^A-Za-z0-9_-]", "_", query["request_id"])[:100] + "_" + r.artifacts.digest(query)[:10]
        path = self.output / "stages" / name
        model = r.pilot.JUDGE if judge else r.pilot.CONSTRUCTOR
        print("STAGE", query["request_id"], "judge" if judge else "constructor", flush=True)
        rows = p._stage(path, [query], ACTIVE_VARIANT, schema, classifier, variant=ACTIVE_VARIANT, model=model, context=CONTEXT)
        costs = probe._cost_stage(path, rows)
        self.stages.append({"request_id": query["request_id"], "path": str(path.relative_to(self.output)),
                            "judge": judge, "status": rows[0]["status"], **costs})
        print("DONE", query["request_id"], rows[0]["status"], "attempts", costs["physical_attempts"], flush=True)
        return rows[0]

    def verify(self, candidates, evidence, prefix):
        decisions, failures, failed_ids = {}, [], set()
        for start in range(0, len(candidates), 12):
            group = candidates[start:start+12]
            query = e.verifier_request(group, evidence, f"{prefix}:verify:{start//12}")
            result = self.call(query, judge=True)
            if result["status"] == "valid":
                decisions.update(result["parsed"])
            else:
                failures.append(query["request_id"])
                failed_ids.update(x["id"] for x in group)
                decisions.update({x["id"]: {"status": "insufficient", "evidence_ids": [],
                    "reason": "Technical verification failure; not a semantic rejection"} for x in group})
        gated = e.gate(candidates, evidence, decisions) if candidates else {"accepted": [], "audit": [], "candidates": []}
        gated["verification_failures"] = failures
        for item in gated["audit"]:
            item["technical_verification_failure"] = item["id"] in failed_ids
        return gated


def run_a(engine, inputs, history, evidence):
    candidates, rounds = [], []
    for category, base, response in zip(r.CATEGORIES, history["requests"], history["responses"]):
        conversation = deepcopy(base["messages"]) + [{"role": "assistant", "content": response["raw_response"]}]
        seen = old._units(category, inputs["baseline"][c.CATEGORIES[category]])
        for number in range(1, 4):
            query = s.glean_request(category, conversation, evidence, number, 3)
            result = engine.call(query)
            if result["status"] != "valid":
                rounds.append({"category": category, "round": number, "stop": "technical_failure"})
                break
            produced = e.assign_candidates(result["parsed"]["candidates"], category, query["request_id"])
            units = old._units(category, [x["value"] for x in produced])
            candidates.extend(produced)
            rounds.append({"category": category, "round": number, "raw_candidates": len(produced),
                           "exact_new_units": len(units - seen)})
            seen |= units
            conversation = query["messages"] + [{"role": "assistant", "content": result["raw_response"]}]
            if number == 3:
                rounds[-1]["stop"] = "declared_round_cap"
                break
            stop = s.stop_request(category, conversation, number)
            answer = engine.call(stop)
            if answer["status"] != "valid" or not answer["parsed"]["continue_search"]:
                rounds[-1]["stop"] = "technical_stop_failure" if answer["status"] != "valid" else "model_stop"
                break
            conversation = stop["messages"] + [{"role": "assistant", "content": answer["raw_response"]}]
    return {**engine.verify(candidates, evidence, "A"), "rounds": rounds}


def run_chunk(engine, inputs, evidence):
    candidates = []
    for query in s.chunk_requests(evidence, inputs["baseline"], 2):
        result = engine.call(query)
        if result["status"] == "valid":
            candidates += e.assign_candidates(result["parsed"]["candidates"], query["category"], query["request_id"])
    return engine.verify(candidates, evidence, "A_chunk")


def run_k(engine, inputs, evidence):
    candidates = []
    queries, coverage = s.completion_requests(inputs, evidence, max_nodes=2)
    for query in queries:
        result = engine.call(query)
        if result["status"] == "valid":
            candidates += e.assign_candidates(result["parsed"]["candidates"], query["category"], query["request_id"])
    gated = engine.verify(candidates, evidence, "K")
    result = engine.call(s.fusion_request(inputs, evidence))
    fusion = {"status": result["status"], "proposals": result.get("parsed"), "graph_mutated": False}
    if result["status"] == "valid":
        query = s.fusion_verifier_request(result["parsed"]["pairs"], inputs, evidence)
        if query:
            checked = engine.call(query, judge=True)
            fusion["verification"] = checked.get("parsed")
            fusion["verification_status"] = checked["status"]
    return {**gated, "coverage": coverage, "fusion": fusion}


def run_b(engine, inputs, evidence):
    from . import grounded_anchors_v4 as b
    inventory = engine.call(b.anchor_request(evidence))
    if inventory["status"] != "valid":
        return {"accepted": [], "candidates": [], "audit": [], "stage_failure": "anchors"}
    restored_anchors = b.restore_anchors(inventory["parsed"], evidence)
    anchors = restored_anchors["anchors"]

    def extract(queries):
        restored = {"candidates": [], "audit": [], "raw_batches": [], "technical_failures": []}
        for query in queries:
            result = engine.call(query)
            if result["status"] == "valid":
                part = b.restore_candidates(query, result["parsed"], evidence, anchors)
                restored["candidates"] += part["candidates"]
                restored["audit"] += part["audit"]
                restored["raw_batches"].append(part)
            else:
                restored["technical_failures"].append(query["request_id"])
        decisions, failed_ids = {}, set()
        for start in range(0, len(restored["candidates"]), 12):
            group = restored["candidates"][start:start+12]
            ids = {x["id"] for x in group}
            subset = {**restored, "candidates": group, "audit": [x for x in restored["audit"] if x["id"] in ids]}
            query = b.verifier_request(subset, evidence, anchors, ident=group[0]["id"] + ":verify")
            result = engine.call(query, judge=True)
            if result["status"] == "valid":
                decisions.update(result["parsed"])
            else:
                restored["technical_failures"].append(query["request_id"])
                failed_ids.update(x["id"] for x in group)
                decisions.update({x["id"]: {"status": "insufficient", "evidence_ids": [],
                    "reason": "Technical verification failure"} for x in group})
        restored["failed_verification_ids"] = sorted(failed_ids)
        coverage = b.accepted_coverage(restored, decisions, evidence, anchors)
        for item in coverage["audit"]:
            item["technical_verification_failure"] = item["id"] in failed_ids
        return restored, decisions, coverage

    def dedup(candidates, prefix):
        proposals = b.propose_duplicates(candidates, threshold=0.5, max_pairs=24)
        decisions = {}
        for start in range(0, len(proposals["pairs"]), 12):
            subset = {**proposals, "pairs": proposals["pairs"][start:start+12]}
            query = b.equivalence_request(candidates, subset, evidence, ident=prefix + f":{start//12}")
            result = engine.call(query, judge=True)
            if result["status"] == "valid":
                decisions.update(result["parsed"])
        return b.deduplicate(candidates, proposals, decisions, evidence)

    initial, initial_decisions, initial_coverage = extract(b.extraction_requests(evidence, anchors))
    first_dedup = dedup(initial_coverage["accepted"], "B:initial:dedup")
    supplement_coverage = deepcopy(initial_coverage)
    supplement_coverage["accepted"] = first_dedup["retained"]
    for category, entry in supplement_coverage.get("coverage_by_category", {}).items():
        entry["accepted"] = [x for x in first_dedup["retained"] if x["category"] == category]
    supplemental, supplemental_decisions, _ = extract(b.supplement_requests(evidence, anchors, supplement_coverage))
    combined = {"candidates": initial["candidates"] + supplemental["candidates"],
                "audit": initial["audit"] + supplemental["audit"]}
    coverage = b.accepted_coverage(combined, {**initial_decisions, **supplemental_decisions}, evidence, anchors)
    failed_ids = set(initial["failed_verification_ids"] + supplemental["failed_verification_ids"])
    for item in coverage["audit"]:
        item["technical_verification_failure"] = item["id"] in failed_ids
    final_dedup = dedup(coverage["accepted"], "B:final:dedup")
    return {"accepted": final_dedup["retained"], "candidates": combined["candidates"], "audit": coverage["audit"],
            "anchor_inventory": restored_anchors, "initial": initial, "supplement": supplemental,
            "initial_coverage": initial_coverage, "final_coverage": coverage,
            "initial_dedup": first_dedup, "final_dedup": final_dedup,
            "verification_failures": initial["technical_failures"] + supplemental["technical_failures"],
            "method_scope": "anchored_initial_and_supplement_extraction_not_just_baseline_hints"}


def run_r(engine, inputs, evidence):
    from . import compiler_grounded_v3 as compiler
    events = [{"id": key, "text": value["text"]} for key, value in inputs["event_index"].items()]
    queries, coverage = compiler.formalization_requests(events, evidence, max_events_per_request=12)
    bindings, decisions, repaired_bindings, repaired_decisions, feedbacks, failures = [], {}, [], {}, [], []
    feedback_failures, feedback_successes = [], 0

    def verify(bound, prefix):
        if not bound["bound_primitives"]:
            return {}
        query = compiler.verifier_request(bound, request_id=prefix + ":verify")
        result = engine.call(query, judge=True, schema=compiler.schema_for, classifier=compiler.classify)
        if result["status"] == "valid":
            return result["parsed"]
        failures.append(query["request_id"])
        return {x["id"]: {"decision": "insufficient", "evidence_ids": [],
                          "reason": "Technical verification failure, not a semantic rejection"}
                for x in bound["bound_primitives"]}

    for query in queries:
        result = engine.call(query, schema=compiler.schema_for, classifier=compiler.classify)
        errors, original_bound, original_decisions = [], None, {}
        if result["status"] == "valid":
            original_bound = compiler.bind_proposals(query, result["parsed"])
            original_decisions = verify(original_bound, query["request_id"])
            bindings.append(original_bound)
            decisions.update(original_decisions)
            local_result = compiler.solve(original_bound, original_decisions)
            errors = compiler.execution_feedback(local_result)
        else:
            failures.append(query["request_id"])
            if result["status"] == "invalid_format" and isinstance(result.get("raw_response"), str):
                errors = compiler.inspect_response(query, result["raw_response"])["errors"]
        replacement, replacement_decisions = original_bound, original_decisions
        if errors:
            feedback = compiler.repair_request(query, result["raw_response"], errors, enabled=True, max_repairs=1)
            attempt = engine.call(feedback, schema=compiler.schema_for, classifier=compiler.classify)
            detail = {"original_request": query["request_id"], "errors": errors,
                      "repair_request": feedback["request_id"], "status": attempt["status"]}
            if attempt["status"] == "valid":
                replacement = compiler.bind_proposals(feedback, attempt["parsed"])
                replacement_decisions = verify(replacement, feedback["request_id"])
                detail["repaired_solution"] = compiler.solve(replacement, replacement_decisions)
                failed_verifier = feedback["request_id"] + ":verify"
                if failed_verifier in failures:
                    feedback_failures.append(failed_verifier)
                else:
                    feedback_successes += 1
            else:
                failures.append(feedback["request_id"])
                feedback_failures.append(feedback["request_id"])
            feedbacks.append(detail)
        if replacement is not None:
            repaired_bindings.append(replacement)
            repaired_decisions.update(replacement_decisions)
    combined = compiler.combine_bindings(bindings) if bindings else None
    solution = (compiler.solve(combined, decisions) if combined else
                {"proposed_primitives": [], "bound_primitives": [], "verifier_supported_primitives": [],
                 "solver_primitives": [], "eligible_primitives": [], "derived": [], "proofs": {},
                 "residual_conflicts": [], "status": "no_valid_original_formalization"})
    # Feedback outcome remains a separate comparison, never silently substituted.
    feedback_solution = (compiler.solve(compiler.combine_bindings(repaired_bindings), repaired_decisions)
                         if feedback_successes and repaired_bindings else None)
    summary = {"status": "partial" if failures else "complete", "coverage": coverage,
               "proposed_atoms": len(solution["proposed_primitives"]),
               "bound_atoms": len(solution["bound_primitives"]),
               "supported_atoms": len(solution["verifier_supported_primitives"]),
               "solver_atoms": len(solution["solver_primitives"]), "eligible_atoms": len(solution["eligible_primitives"]),
               "derived_edges": len(solution["derived"]), "invalid_proofs": sum(not x for x in solution["proofs"].values()),
               "residual_conflicts": len(solution["residual_conflicts"]), "feedback_attempts": len(feedbacks),
               "feedback_derived_edges": len(feedback_solution["derived"]) if feedback_solution else None,
               "feedback_status": ("not_triggered" if not feedbacks else "partial" if feedback_successes and feedback_failures
                                   else "complete" if feedback_successes else "failed"),
               "feedback_failures": feedback_failures, "valid_original_batches": len(bindings),
               "technical_failures": failures, "native_f1_changed": False}
    return {"summary": summary, "binding": combined, "solution": solution,
            "feedback": feedbacks, "feedback_solution": feedback_solution}


def _summarize_arm(inputs, report):
    accepted = report.get("accepted", [])
    row = e.merge_native(inputs["baseline"], accepted)["native_row"]
    counts = {}
    for category, field in c.CATEGORIES.items():
        before = old._units(category, inputs["baseline"][field])
        after = old._units(category, row[field])
        counts[category] = {"baseline_units": len(before), "new_exact_units": len(after-before), "total_units": len(after)}
    return {"candidate_records": len(report.get("candidates", [])), "accepted_records": len(accepted),
            "verdicts": dict(Counter(x["verdict"]["status"] for x in report.get("audit", []) if not x.get("technical_verification_failure"))),
            "bound_records": sum(x.get("reference_bound", x["bound"]) for x in report.get("audit", [])),
            "counts": counts, "verification_failures": report.get("verification_failures", []),
            "merge_protocol": "occurrence_preserving_v2",
            "event_occurrence_records": len(row[c.CATEGORIES["event"]]),
            "event_identity_claim": False}


def execute(source, baseline, base_stage, output, *, methods=("A", "A_chunk", "B", "K", "R"), resume=False):
    raise ValueError("grounded_methods_pilot_v1 is historical; use the explicit grounded_methods_pilot_v2 contract")


def _active_execute(source, baseline, base_stage, output, *, methods=("A", "A_chunk", "B", "K", "R"), resume=False):
    output = Path(output).resolve()
    manifest = _active_preflight(source, baseline, base_stage, output, methods=methods)
    inputs, history = old.load_inputs(source, baseline, base_stage)
    evidence = e.catalog(inputs["source"])
    if output.exists():
        if not resume:
            raise ValueError("Existing run requires explicit resume")
        p._same(output / "input_manifest.json", manifest)
    elif resume:
        raise ValueError("Missing run cannot resume")
    else:
        output.mkdir(parents=True)
    with immutable_publish.publication_scope(True), retry_continuation.execution_lock(output):
        r.immutable(output / "input_manifest.json", manifest)
        r.immutable(output / "evidence_catalog.json", evidence)
        engine, summaries = Engine(output), {}
        for method in methods:
            if method == "A":
                report = run_a(engine, inputs, history, evidence)
            elif method == "A_chunk":
                report = run_chunk(engine, inputs, evidence)
            elif method == "K":
                report = run_k(engine, inputs, evidence)
            elif method == "B":
                report = run_b(engine, inputs, evidence)
            else:
                report = run_r(engine, inputs, evidence)
            r.immutable(output / "arms" / method / "report.json", report)
            if method != "R":
                merged = e.merge_native(inputs["baseline"], report["accepted"])
                r.immutable(output / "arms" / method / "merge.json", merged)
                p._bytes(output / "arms" / method / "extraction.jsonl", (json.dumps(merged["native_row"], ensure_ascii=False) + "\n").encode("utf-8"))
                summaries[method] = _summarize_arm(inputs, report)
            else:
                summaries[method] = report["summary"]
        all_calls = [call for stage in engine.stages for call in r.pilot._records(output / stage["path"] / "calls.jsonl")]
        summary = {"variant": ACTIVE_VARIANT, "status": "complete" if all(x["status"] == "valid" for x in engine.stages) else "partial",
                   "arms": summaries, "stages": engine.stages, "logical_requests": len(engine.stages),
                   "physical_calls": len(all_calls), "costs": m._costs(all_calls),
                   "quality_claim": "source-verifier decisions, not native F1 or gold accuracy"}
        r.immutable(output / "summary.json", summary)
        return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for key in ("source", "baseline", "base-stage", "output"):
        parser.add_argument("--" + key, type=Path, required=True)
    parser.add_argument("--methods", nargs="+", default=["A", "A_chunk", "B", "K", "R"])
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--resume", action="store_true")
    args = vars(parser.parse_args())
    live, resume = args.pop("execute"), args.pop("resume")
    if resume and not live:
        parser.error("--resume requires --execute")
    result = execute(**args, resume=resume) if live else preflight(**args)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
