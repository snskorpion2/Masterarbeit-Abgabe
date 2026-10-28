"""Approved five-arm local recall pilot, isolated from the strict reference entrypoint."""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import sys
import time

from . import recall_methods as methods, reliability_v2 as r
from . import retry_continuation

VARIANT = "local_lamport_recall_methods_v1"
TRIPLES_ONLY_VARIANT = "local_lamport_recall_methods_triples_only_v1"
ARM_DEPENDENCIES = {
    "baseline": ["original_base"],
    "glean": ["original_base", "glean"],
    "anchors": ["original_base", "source_anchors", "anchors"],
    "decomposition": ["preprocessing", "decomposed_base"],
    "all": ["preprocessing", "decomposed_base", "all_glean", "source_anchors", "all_anchors"],
}


class InvalidConstruction(RuntimeError):
    """A technically invalid prerequisite cannot silently turn into a baseline arm."""


def preflight(output, questions_path=r.pilot.QUESTIONS, *, include_mcqs=True):
    pre = (r.preflight(Path(output), Path(questions_path)) if include_mcqs else
           r.preflight(Path(output), Path(questions_path), include_mcqs=False))
    pre.update(variant=VARIANT if include_mcqs else TRIPLES_ONLY_VARIANT,
               arm_order=list(methods.ARM_ORDER), constructions=5,
               shared_native_extractions=2,
               combination_order=["preprocessing", "extraction", "glean", "anchors"],
               arm_dependencies=ARM_DEPENDENCIES, source_unit_rule="all_nonempty_paragraphs_v1",
               merge_rule="exact_additional_triples_and_exact_event_entity_union_v1",
               source_policy="original_source_for_judgments_mcq_and_all_supplements",
               anchor_policy="exact_source_quote_and_case_sensitive_unused_lexical_hint_not_fact_test",
               extraction_output_tokens=2048, preprocessing_output_tokens=8192, anchor_output_tokens=4096,
               shared_cost_policy="physical_once_and_per_arm_standalone_attributable",
               factual_source_preservation="prompt_requested_not_guaranteed_by_structural_validation")
    if not include_mcqs:
        pre["source_policy"] = "original_source_for_judgments_and_all_supplements"
    return pre


def costs(calls):
    """Sum observed measurements, explicitly flagging partial sums as lower bounds.

    None and absence mean unmeasured, never measured zero. Cache accounting is
    optional and cannot erase a known logical-input count. The historical helper
    remains unchanged; only this new variant uses the stricter completeness contract.
    """
    calls = list(calls)
    required = ("logical_prompt_tokens", "output_tokens", "elapsed_seconds", "backend_duration_seconds")
    observed = {name: [] for name in (*required, "cached_prompt_tokens", "uncached_prompt_tokens")}
    normalized = []
    token_gaps = 0

    def measurement(container, key, *, integer=False):
        value = container.get(key)
        if value is None:
            return None
        allowed = (int,) if integer else (int, float)
        try:
            valid = type(value) in allowed and math.isfinite(value) and value >= 0
        except OverflowError:
            valid = False
        if not valid:
            raise ValueError(f"Invalid raw cost measurement: {key}")
        return value

    for call in calls:
        response = call.get("response")
        if response is None:
            response = {}
        if not isinstance(response, dict):
            raise ValueError("Invalid raw cost response container")
        prompt = measurement(response, "prompt_eval_count", integer=True)
        output = measurement(response, "eval_count", integer=True)
        cached = measurement(response, "prompt_eval_cached_count", integer=True)
        elapsed = measurement(call, "elapsed_seconds")
        duration = measurement(response, "total_duration")
        if prompt is not None and cached is not None and cached > prompt:
            raise ValueError("Cached input tokens exceed complete input tokens")
        uncached = prompt - cached if prompt is not None and cached is not None else None
        values = (prompt, output, elapsed, None if duration is None else duration / 1e9, cached, uncached)
        for name, value in zip(observed, values):
            if value is not None:
                observed[name].append(value)
        token_gaps += prompt is None or output is None
        # The helper's default cache=0 is only an internal numeric placeholder.
        # Both cache totals and their completeness are replaced below from observed values.
        clean_response = {**response, "prompt_eval_cached_count": cached if cached is not None else 0}
        normalized.append({**call, "response": clean_response, "elapsed_seconds": elapsed if elapsed is not None else 0})
    result = retry_continuation.costs(normalized)
    result.update({name: sum(values) for name, values in observed.items()})
    result["calls_without_token_usage"] = token_gaps
    if any(type(value) not in (int, float) or not math.isfinite(value) or value < 0 for value in result.values()):
        raise ValueError("Nonfinite or negative cost aggregate")
    result["measurement_completeness"] = {
        name: {"known_calls": len(values), "missing_calls": len(calls) - len(values),
               "complete": len(values) == len(calls), "sum_is_lower_bound": len(values) != len(calls)}
        for name, values in observed.items()}
    result["required_measurements_complete"] = all(result["measurement_completeness"][name]["complete"]
                                                   for name in required)
    return result


def _calls(paths):
    # Unique directories keep reused construction records out of actual totals twice.
    records = []
    files = set()
    for path in paths:
        for file in Path(path).rglob("calls.jsonl"):
            files.add(file.resolve())
    for file in sorted(files):
        records.extend(r.pilot._records(file))
    return records


def cost_report(output, arms):
    by_stage = {name: [] for name in ("construction", "judgment", "mcq", "confidence")}
    for path in output.rglob("calls.jsonl"):
        relative = path.relative_to(output)
        stage = ("construction" if relative.parts[0] == "construction" else
                 "judgment" if path.parent.name == "triple_judgments" else
                 "mcq" if path.parent.name == "mcq_answers" else "confidence")
        by_stage[stage].extend(r.pilot._records(path))
    claimed = set()
    for arm in arms:
        dependencies = arm["construction_dependencies"]
        own = [name for name in dependencies if name not in claimed]
        claimed.update(dependencies)
        shared_paths = [output / "construction" / name for name in dependencies]
        actual_paths = [output / "construction" / name for name in own]
        evaluation_path = output / "arms" / arm["arm"]
        arm["costs"] = {
            "actual": costs(_calls([*actual_paths, evaluation_path])),
            "standalone_attributable": costs(_calls([*shared_paths, evaluation_path])),
            "actual_construction_stages_charged_here": own,
            "reused_construction_stages": [x for x in dependencies if x not in own],
            "by_stage_actual": {"construction": costs(_calls(actual_paths)),
                                "judgment": costs(_calls([evaluation_path / "triple_judgments"])),
                                "mcq": costs(_calls([evaluation_path / "mcq_answers"])),
                                "confidence": costs(_calls([evaluation_path / "confidence_nemotron",
                                                            evaluation_path / "confidence_qwen"]))}}
    return {"actual": costs(_calls([output])), "by_stage_actual": {key: costs(value) for key, value in by_stage.items()},
            "units": "tokens_and_measured_seconds_not_euros_or_energy",
            "attributable_is_not_additional_physical_usage": True}


def _persist_row(path, row):
    if not path.exists():
        r.pilot._append(path, row)
    elif r.pilot._records(path) != [row]:
        raise ValueError("Immutable recall extraction changed")


def execute(output, pre, *, resume=False):
    include_mcqs = pre.get("evaluation_scope") != "triples_only"
    expected_variant = VARIANT if include_mcqs else TRIPLES_ONLY_VARIANT
    if pre.get("variant") != expected_variant:
        raise ValueError("Preflight evaluation scope and variant disagree")
    output = Path(output).resolve()
    checkpoint = output / "technical_summary.json"
    if output.exists():
        if not resume or not checkpoint.is_file():
            raise ValueError("Existing output requires --resume and a matching checkpoint")
        prior = json.loads(checkpoint.read_text(encoding="utf-8"))
        if prior.get("preflight") != pre:
            raise ValueError("Resume inputs, code or method contract changed")
    else:
        if resume:
            raise ValueError("Cannot resume a missing output directory")
        output.mkdir(parents=True)
        prior = {}
    summary = {"preflight": pre, "variant": expected_variant, "status": "running", "analysis_performed": False,
               "started_utc": prior.get("started_utc", r.pilot._now()),
               "resume_count": prior.get("resume_count", -1) + 1,
               "active_seconds": prior.get("active_seconds", 0), "arms": [], "construction_counts": {},
               "retry_policy": r.technical_retry_policy()}
    if not include_mcqs:
        summary.update(evaluation_scope="triples_only", disabled_stages=list(r.DISABLED_MCQ_STAGES))
    started = time.perf_counter()
    with retry_continuation.execution_lock(output):
        r.write_json(checkpoint, summary)
        try:
            raw_source = r.pilot.ARTICLE.read_text(encoding="utf-8-sig")
            source = methods.normalize(raw_source)
            units = methods.source_units(raw_source)
            if r.sha256(r.pilot.ARTICLE) != pre["article_sha256"]:
                raise ValueError("Original source changed after preflight")
            input_manifest = {"article_path": str(r.pilot.ARTICLE),
                        "article_sha256": pre["article_sha256"], "original_source": raw_source,
                        "native_normalized_source": source, "source_units": units,
                        "source_sha256": r.artifacts.digest(source)}
            if not include_mcqs:
                input_manifest.update(evaluation_scope="triples_only", disabled_stages=list(r.DISABLED_MCQ_STAGES))
            r.immutable(output / "input_manifest.json", input_manifest)
            revised, provenance = r.frozen_questions.prepare(Path(pre["questions_path"]), r.pilot.ARTICLE)
            if provenance != pre["question_version"] or r.artifacts.digest(revised) != pre["revised_questions_sha256"]:
                raise ValueError("Frozen questions changed after preflight")
            questions_path = r.frozen_questions.persist(output / "frozen_questions", revised, provenance)
            questions = r.artifacts.load_questions(questions_path)
            producers, shared = {}, {}
            all_results = []

            def construct(name, schedule):
                results = r.requests(output / "construction" / name, schedule, r.pilot.CONSTRUCTOR,
                                     variant=expected_variant)
                all_results.extend(results)
                summary["construction_counts"][name] = r.stage_attempt_counts(results)
                for request, result in zip(schedule, results):
                    producers[request["request_id"]] = {"request": request, "result": result}
                if any(result["status"] != "valid" for result in results):
                    raise InvalidConstruction(name)
                return results

            def supplement(state, method, name, anchors=None):
                schedule = methods.supplement_requests(source, state, method, name, anchors)
                return methods.merge_additions(state, schedule, construct(name, schedule))

            for arm in methods.ARM_ORDER:
                arm_summary = {"arm": arm, "status": "running", "construction_dependencies": ARM_DEPENDENCIES[arm]}
                summary["arms"].append(arm_summary)
                r.write_json(checkpoint, summary)
                if arm == "baseline":
                    schedule = methods.extraction_requests(source, "original_base")
                    shared["original_base"] = methods.extraction_state(schedule, construct("original_base", schedule))
                    state = shared["original_base"]
                elif arm == "glean":
                    state = supplement(shared["original_base"], "glean", "glean")
                elif arm == "anchors":
                    shared["anchors"] = construct("source_anchors", [methods.anchor_request(units)])[0]["parsed"]["anchors"]
                    state = supplement(shared["original_base"], "anchors", "anchors", shared["anchors"])
                elif arm == "decomposition":
                    response = construct("preprocessing", [methods.preprocessing_request(units)])[0]["parsed"]
                    view = methods.resolved_view(units, response)
                    r.immutable(output / "derived_source.json", {"source_units": units, "resolved_statements": response,
                                "extraction_view": view, "original_source_sha256": r.artifacts.digest(source),
                                "factual_fidelity": "not_established_by_structural_validation"})
                    schedule = methods.extraction_requests(view, "decomposed_base")
                    shared["decomposed_base"] = methods.extraction_state(schedule, construct("decomposed_base", schedule))
                    state = shared["decomposed_base"]
                else:
                    state = supplement(shared["decomposed_base"], "glean", "all_glean")
                    state = supplement(state, "anchors", "all_anchors", shared["anchors"])
                folder = output / "arms" / arm
                folder.mkdir(parents=True, exist_ok=True)
                row = methods.extraction_row(state, source)
                extraction_path = folder / "extraction.jsonl"
                _persist_row(extraction_path, row)
                r.immutable(folder / "construct_provenance.json", {"arm": arm, "variant": expected_variant,
                            "construction_dependencies": ARM_DEPENDENCIES[arm], "state": state,
                            "original_source_sha256": r.artifacts.digest(source)})
                inventory = {"construction_id": arm, "items": r.artifacts.inventory_extraction(extraction_path, arm),
                             "concepts": [], "induction_enabled": False, "extraction_file": str(extraction_path),
                             "extraction_sha256": r.sha256(extraction_path), "questions_file": str(questions_path),
                             "questions_sha256": r.sha256(questions_path),
                             "native_context_record": r.artifacts.native_context_record(extraction_path, questions)}
                r.immutable(folder / "inventory.json", inventory)
                ne_items = methods.confidence_items(inventory, state, producers)
                r.immutable(folder / "producer_provenance.json", ne_items)
                assessed = (r.assess_extraction(folder, inventory, row, ne_items, variant=VARIANT)
                            if include_mcqs else r.assess_extraction(folder, inventory, row, ne_items,
                                                                      variant=expected_variant, include_mcqs=False))
                arm_results = [entry for rows in assessed.values() for entry in rows]
                all_results.extend(arm_results)
                arm_summary["technical_counts"] = {name: r.stage_attempt_counts(rows) for name, rows in assessed.items()}
                if not include_mcqs:
                    arm_summary["technical_counts"].update({name: {"status": "disabled"}
                                                            for name in r.DISABLED_MCQ_STAGES})
                arm_summary["status"] = ("technically_complete_uninterpreted" if all(x["status"] == "valid" for x in arm_results)
                                         else "technical_gaps_uninterpreted")
                summary["costs"] = cost_report(output, summary["arms"])
                r.write_json(checkpoint, summary)
            if r.sha256(r.pilot.ARTICLE) != pre["article_sha256"] or r.sha256(Path(pre["questions_path"])) != pre["questions_sha256"]:
                raise ValueError("Frozen source or questions changed during collection")
            r.verify_source(r.DEFAULT_SOURCE)
            summary["technical_counts"] = r.stage_attempt_counts(all_results)
            complete = all(x["status"] == "valid" for x in all_results)
            summary["status"] = "technically_complete_uninterpreted" if complete else "technical_gaps_uninterpreted"
            return 0 if complete else 2
        except InvalidConstruction as exc:
            summary.update(status="technical_gaps_uninterpreted", failed_dependency=str(exc))
            summary["arms"][-1]["status"] = "invalid_construction_dependency"
            return 2
        except BaseException as exc:
            summary.update(status="failed_checkpoint", error_type=type(exc).__name__, error_message=str(exc))
            raise
        finally:
            summary["costs"] = cost_report(output, summary["arms"])
            summary.update(finished_utc=r.pilot._now(), active_seconds=summary["active_seconds"] + time.perf_counter() - started)
            summary["artifact_hashes"] = {str(path.relative_to(output)): r.sha256(path) for path in output.rglob("*")
                                          if path.is_file() and path not in (checkpoint, output / "execution.lock")}
            r.write_json(checkpoint, summary)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--questions-input", type=Path, default=r.pilot.QUESTIONS)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--include-mcqs", action="store_true",
                        help="Enable the historical full MCQ evaluation scope explicitly")
    args = parser.parse_args(argv)
    if args.resume and not args.execute:
        parser.error("--resume requires --execute")
    pre = preflight(args.output, args.questions_input.resolve(), include_mcqs=args.include_mcqs)
    if not args.execute:
        print(json.dumps(pre, ensure_ascii=False, indent=2))
        return 0
    if r.request_json("/api/ps").get("models"):
        raise RuntimeError("Ollama has a loaded model; recall pilot will not take over an existing model")
    return execute(args.output, pre, resume=args.resume)


if __name__ == "__main__":
    sys.dont_write_bytecode = True
    raise SystemExit(main())
