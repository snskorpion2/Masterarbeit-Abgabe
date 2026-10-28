"""Passive native judgments, independent source audit and physical cost ledger.

``evaluation/summary.json`` is the exporter interface (schema_version=1).
Source labels live only in ``evaluation/source_audit.json`` and are never used
to build a model request. Construction checkpoints are never rewritten here.
"""
from __future__ import annotations

from collections import Counter
from copy import deepcopy
import json
from pathlib import Path
import random

from . import completion_contracts as c, reliability_v2 as r
from . import recall_pilot, retry_continuation, temporal_reasoner
from .contract import sha256

SEED = 27092026
PROTOCOL = "completion_measurements_v1"


def _read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def _index(rows, key="request_id"):
    result = {}
    for row in rows:
        ident = row[key]
        if ident in result:
            raise ValueError(f"Duplicate {key}: {ident}")
        result[ident] = row
    return result


def _joined(schedule, results):
    requests, responses = _index(schedule), _index(results)
    if requests.keys() != responses.keys():
        raise ValueError("Unassignable or missing response IDs")
    return [(req, responses[ident]) for ident, req in requests.items()]


def metric_rows(schedule, results):
    """Join by IDs and semantic coordinates, never by dispatch position."""
    paired = {}
    for request, result in _joined(schedule, results):
        key = request["repeat"], request["category"], request["kind"]
        if key in paired:
            raise ValueError("Duplicate measurement coordinate")
        paired[key] = request, result
    rows = []
    for repeat in range(1, 4):
        for category in r.CATEGORIES:
            req, incorrect = paired[repeat, category, "incorrect"]
            missing = paired[repeat, category, "more"][1]
            if incorrect["status"] == "valid":
                wrong = incorrect["parsed"]["incorrect_ids"]
                if len(wrong) != len(set(wrong)) or not set(wrong) <= set(req["item_ids"]):
                    raise ValueError("Unassignable incorrect candidate IDs")
            rows.append({"repeat": repeat, "category": category,
                         **r.metrics(len(req["item_ids"]), incorrect, missing, category)})
    return rows


def audit_template(candidates: list[dict], primitives: list[dict]) -> dict:
    """Unassessed is null. Counter-review is an explicit, independent record."""
    def entries(rows):
        _index(rows, "id")
        return [{"id": row["id"], "item": deepcopy(row), "correctness": None,
                 "novelty": None, "source_reason": None, "reviewer": None,
                 "cross_check": None, "error_types": []} for row in rows]
    return {"schema_version": 1, "review_type": "assistant_source_audit_not_gold",
            "candidates": entries(candidates), "primitives": entries(primitives)}


def summarize_audit(audit: dict, proofs: dict) -> dict:
    """Truth, novelty, compiler errors and proof validity are independent axes.

    proofs maps conclusion ID to {valid: bool, primitive_ids: list[str]}.
    A valid derivation with an incorrect primitive remains valid but unsound
    as a source claim. Null/unclear primitive judgments are never promoted.
    """
    result = {"review_type": audit["review_type"], "complete": True, "proofs": {}}
    for kind in ("candidates", "primitives"):
        rows = audit[kind]
        _index(rows, "id")
        for row in rows:
            if row["correctness"] not in (None, "correct", "incorrect", "unclear"):
                raise ValueError("Unknown correctness label")
            if row["novelty"] not in (None, "new_source_content", "new_explicit_representation", "already_present"):
                raise ValueError("Unknown novelty label")
            if row["correctness"] != "correct" and row["novelty"] is not None:
                raise ValueError("Novelty cannot count non-correct information")
            if row["correctness"] is not None and (not row["source_reason"] or not row["reviewer"]):
                raise ValueError("Assessed labels require evidence and reviewer")
            if not set(row["error_types"]) <= {"source_error", "time_error", "role_error", "formalization_error"}:
                raise ValueError("Unknown source/compiler error type")
        labels = Counter(row["correctness"] for row in rows)
        clear = labels["correct"] + labels["incorrect"]
        cross_checked = sum(bool(row["cross_check"] and row["cross_check"].get("reviewer")
                                 and row["cross_check"].get("verdict") == "confirmed"
                                 and row["cross_check"]["reviewer"] != row["reviewer"])
                            for row in rows)
        result[kind] = {"total": len(rows), "correct": labels["correct"], "incorrect": labels["incorrect"],
                        "unclear": labels["unclear"], "unassessed": labels[None],
                        "precision": labels["correct"] / clear if clear else None,
                        "precision_denominator": "correct_plus_incorrect_excludes_unclear_and_unassessed",
                        "cross_checked": cross_checked,
                        **{novelty: sum(row["novelty"] == novelty for row in rows) for novelty in
                           ("new_source_content", "new_explicit_representation", "already_present")},
                        "errors": dict(Counter(error for row in rows for error in row["error_types"]))}
        result["complete"] &= cross_checked == len(rows) and not labels[None]
        if kind == "candidates":
            result["complete"] &= all(row["correctness"] != "correct" or row["novelty"] is not None for row in rows)
    primitives = _index(audit["primitives"], "id")
    for ident, proof in proofs.items():
        if type(proof["valid"]) is not bool or not set(proof["primitive_ids"]) <= primitives.keys():
            raise ValueError("Invalid proof audit references")
        truths = [primitives[x]["correctness"] for x in proof["primitive_ids"]]
        truth = ("incorrect" if "incorrect" in truths else None if not truths or None in truths else
                 "unclear" if "unclear" in truths else "correct")
        result["proofs"][ident] = {**proof, "premise_correctness": truth}
    result["invalid_proof_count"] = sum(not proof["valid"] for proof in proofs.values())
    return result


def _costs(calls):
    report = recall_pilot.costs(calls)
    # Preserve observed lower bounds separately. Unknown full totals are null.
    report["observed_lower_bounds"] = {}
    for field, coverage in report["measurement_completeness"].items():
        if not coverage["complete"]:
            report["observed_lower_bounds"][field] = report[field] if coverage["known_calls"] else None
            report[field] = None
    report["physical_inference_dispatches"] = sum(x.get("inference_dispatched") is True for x in calls)
    return report


def cost_report(output: Path, dependencies: dict) -> dict:
    """Count unique local raw transports once, not once per arm/decision consumer."""
    paths = ["construction/completion", "compilation/baseline", "compilation/additions",
             "evaluation/judgments", "evaluation/judge_confidence", "evaluation/producer_confidence"]
    calls, stages = {}, {}
    for relative in paths:
        rows = r.pilot._records(output / relative / "calls.jsonl")
        _index(rows, "request_identity")
        for row in rows:
            ident = row["request_identity"]
            if ident in calls:
                raise ValueError("Duplicate physical dispatch identity across stages")
            calls[ident] = row
        finals = output / relative / "final_responses.json"
        stages[relative] = {"costs": _costs(rows),
                            "attempts": r.stage_attempt_counts(_read(finals)) if finals.exists() else None}
    return {"actual_costs": _costs(list(calls.values())), "stages": stages,
            "historical_baseline": "reused_not_charged", "logical_reuse": dependencies,
            "reasoner_seconds": {name: _read(output / "reasoning" / name / "result.json")["elapsed_seconds"]
                                 for name in ("baseline", "combined")}}


def _confidence(schedule, results):
    requests = []
    for request, result in _joined(schedule, results):
        item = {"id": request["request_id"], "event": "id_triple_judgment",
                "original_input": r._request_messages(request), "original_response": result.get("raw_response")}
        confidence = r.confidence_request(request["request_id"] + ":confidence", [item])
        if result["status"] != "valid":
            confidence["skip_reason"] = "invalid_prior_result"
        requests.append(confidence)
    return requests


def _producer_confidence(producers):
    grouped = {}
    for decision, producer in producers.items():
        if producer["kind"] not in ("completion", "formalization") or producer["decision_id"] != decision:
            raise ValueError("Unknown producer decision or solver confidence")
        request, result = producer["request"], producer["result"]
        if producer["request_id"] != request["request_id"] or request["request_id"] != result["request_id"]:
            raise ValueError("Producer request/response mismatch")
        key = producer["kind"], request["request_id"], result["status"]
        item = {"id": decision, "event": "id_triple_judgment",
            "decision_id": decision, "item_id": producer["item_id"],
            "original_input": r._request_messages(request),
            "original_response": result.get("raw_response")}
        if producer["kind"] == "completion":
            prefix = request["source_id"] + ":" + request["request_id"] + ":"
            if not decision.startswith(prefix) or result["status"] != "valid":
                raise ValueError("Completion decision lacks a valid original candidate")
            index = int(decision[len(prefix):])
            candidates = result["parsed"]["candidates"]
            if not 0 <= index < len(candidates) or decision != prefix + f"{index:05d}":
                raise ValueError("Unassignable completion decision ID")
            item.update(candidate_index=index, candidate=deepcopy(candidates[index]))
        grouped.setdefault(key, []).append(item)
    requests = []
    for (kind, _, status), items in grouped.items():
        for start in range(0, len(items), r.pilot.CONFIDENCE_BATCH):
            req = r.confidence_request(f"producer-confidence:{len(requests):05d}", items[start:start + r.pilot.CONFIDENCE_BATCH])
            # Reuse fixed-ID wire protocol and shared producer compression, but
            # bind the new confidence target locally without changing old methods.
            prefix, payload = req["prompt"].rsplit("\n", 1)
            payload = json.loads(payload)
            for item in payload["items"]:
                item["event"] = kind + "_decision"
                item["confidence_target"] = (
                    "The indicated completion candidate is supported by the provided source."
                    if kind == "completion" else
                    "The indicated item's temporal formalization (including unformalized status) faithfully represents the provided native item, its event identity, polarity and date role. This is not confidence in source truth or solver conclusions.")
            req["prompt"] = prefix + "\n" + json.dumps(payload, ensure_ascii=False, allow_nan=False)
            req["decision_kind"] = kind
            if status != "valid":
                req["skip_reason"] = "invalid_prior_result"
            requests.append(req)
    return requests


def _stage(output, name, schedule, model, *, audit_only=False):
    from . import completion_pilot as p
    path = output / "evaluation" / name
    contract, budget = p._stage_contract(schedule, PROTOCOL, r.schema_for)
    contract["model"] = model
    p._same(path / "schedule.json", contract)
    p._same(path / "budget.json", budget)
    if path.exists():
        intents, attempts, raw = r.audit_existing(path, schedule, model)
        if any(x["attempt_id"] not in attempts and x["attempt_id"] not in raw for x in intents):
            raise RuntimeError("Unknown in-flight evaluation outcome")
        if intents and (not (path / "schedule.json").exists() or not (path / "budget.json").exists()):
            raise ValueError("Dispatched measurement lacks contract")
    if audit_only:
        return
    r.immutable(path / "schedule.json", contract)
    r.immutable(path / "budget.json", budget)
    results = r.requests(path, schedule, model, variant=p.VARIANT, schema_fn=r.schema_for,
                         classifier_fn=r.classify, protocol_id=PROTOCOL)
    _joined(schedule, results)
    return results


def evaluate(output: Path, arm_inputs: dict, producers: dict) -> dict:
    """Run under the same directory lock as construction, including read validation."""
    output = Path(output).resolve()
    with retry_continuation.execution_lock(output):
        return _evaluate_locked(output, arm_inputs, producers)


def _evaluate_locked(output, arm_inputs, producers):
    from . import completion_pilot as p
    if not all((output / name).is_file() for name in ("input_manifest.json", "arm_inputs.json", "producers.json")):
        raise ValueError("Evaluation requires frozen construction checkpoints")
    p._same(output / "input_manifest.json", p.preflight(output))
    p._same(output / "arm_inputs.json", arm_inputs)
    p._same(output / "producers.json", producers)
    if set(arm_inputs) != set(p.ARMS):
        raise ValueError("Expected exactly four arms")
    native, arms, schedules = {}, {}, []
    base_inventory = r.artifacts.inventory_extraction(c.BASELINE, "baseline")
    for arm in p.ARMS:
        entry = arm_inputs[arm]
        path = (output / entry["native_input_path"]).resolve()
        if not path.is_relative_to(output) or sha256(path) != entry["native_input_hash"]:
            raise ValueError("Native input hash/path mismatch")
        digest = entry["native_input_hash"]
        ident = "native:" + digest
        arms[arm] = {**entry, "measurement_id": ident}
        if ident in native:
            continue
        inventory = r.artifacts.inventory_extraction(path, "baseline")
        _index(inventory, "occurrence_id")
        by_id = _index(inventory, "occurrence_id")
        if any(by_id.get(item["occurrence_id"]) != item for item in base_inventory):
            raise ValueError("Baseline occurrence IDs or values changed in combined input")
        rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
        if len(rows) != 1:
            raise ValueError("Expected single native source")
        schedule = r.judge_requests({"construction_id": ident, "items": inventory}, rows[0])
        for req in schedule:
            req["parameters"] = {"max_new_tokens": 4096}
            req["native_input_hash"] = digest
        schedules.extend(schedule)
        native[ident] = {"native_input_hash": digest, "inventory": inventory}
    if len(native) > 2 or arms["baseline"]["measurement_id"] != arms["reasoning"]["measurement_id"] or arms["completion"]["measurement_id"] != arms["completion_reasoning"]["measurement_id"]:
        raise ValueError("Reasoning changed native measurement input")
    rng = random.Random(SEED)
    shuffled = []
    for repeat in range(1, 4):
        block = [q for q in schedules if q["repeat"] == repeat]
        rng.shuffle(block)
        shuffled.extend(block)
    producer_schedule = _producer_confidence(producers)
    # Audit all existing stages before dispatching or writing any new artifacts.
    _stage(output, "judgments", shuffled, r.pilot.JUDGE, audit_only=True)
    _stage(output, "producer_confidence", producer_schedule, r.pilot.CONSTRUCTOR, audit_only=True)
    prior = output / "evaluation/judgments/final_responses.json"
    if prior.exists():
        _stage(output, "judge_confidence", _confidence(shuffled, _read(prior)), r.pilot.JUDGE, audit_only=True)
    elif (output / "evaluation/judge_confidence").exists():
        raise ValueError("Judge confidence without judgment checkpoint")
    judged = _stage(output, "judgments", shuffled, r.pilot.JUDGE)
    confidence_schedule = _confidence(shuffled, judged)
    judge_confidence = _stage(output, "judge_confidence", confidence_schedule, r.pilot.JUDGE)
    producer_results = _stage(output, "producer_confidence", producer_schedule, r.pilot.CONSTRUCTOR)
    judged_by_id, conf_by_id = _index(judged), _index(judge_confidence)
    for ident, record in native.items():
        schedule = [q for q in shuffled if q["native_input_hash"] == record["native_input_hash"]]
        results = [judged_by_id[q["request_id"]] for q in schedule]
        record.update(schedule=schedule, judgments=results, metrics=metric_rows(schedule, results),
                      judge_confidence=[conf_by_id[q["request_id"] + ":confidence"] for q in schedule])
    primitives, proofs = {}, {}
    for name in ("baseline", "combined"):
        terminal = _read(output / "reasoning" / name / "primitives.json")
        derived = _read(output / "reasoning" / name / "result.json")["derived"]
        for primitive in terminal:
            if primitive["id"] in primitives and primitives[primitive["id"]] != primitive:
                raise ValueError("Conflicting shared primitive ID")
            primitives[primitive["id"]] = primitive
        # Terminal dependency IDs are reconstructed from each proof's source tree.
        by_id = _index(derived, "id")
        terminal_ids = {x["id"] for x in terminal}
        def leaves(ident, active=frozenset()):
            if ident in terminal_ids:
                return {ident}
            if ident in active or ident not in by_id:
                return set()
            return set().union(*(leaves(x, active | {ident}) for x in by_id[ident]["premise_ids"]))
        for conclusion in derived:
            proof = {"valid": temporal_reasoner.verify_proof(conclusion, terminal, derived),
                     "primitive_ids": sorted(leaves(conclusion["id"])),
                     "rule_id": conclusion["rule_id"], "source_item_ids": conclusion["source_item_ids"]}
            if conclusion["id"] in proofs and proofs[conclusion["id"]] != proof:
                raise ValueError("Shared proof verification differs")
            proofs[conclusion["id"]] = proof
    candidates = _read(output / "construction/bound_candidates.json")["candidates"]
    template = audit_template(candidates, list(primitives.values()))
    audit_path = output / "evaluation/source_audit.json"
    # An editable audit is bound to immutable item content, never fed to requests.
    audit = _read(audit_path) if audit_path.exists() else template
    for kind in ("candidates", "primitives"):
        if [{"id": x["id"], "item": x["item"]} for x in audit[kind]] != [{"id": x["id"], "item": x["item"]} for x in template[kind]]:
            raise ValueError("Source audit items differ from frozen construction")
    audit_summary = summarize_audit(audit, proofs)
    if not audit_path.exists():
        r.immutable(audit_path, audit)
    result = {"schema_version": 1, "variant": p.VARIANT, "shuffle_seed": SEED,
              "status": "complete" if all(x["status"] == "valid" for x in judged + judge_confidence + producer_results) else "partial",
              "arms": arms, "native_measurements": native,
              "producer_confidence": {"schedule": producer_schedule, "results": producer_results},
              "source_audit_path": "evaluation/source_audit.json", "source_audit": audit_summary,
              "proofs": proofs, "paused_stages": p.PAUSED,
              "costs": cost_report(output, {"native_arm_references": 4, "unique_native_measurements": len(native),
                                            "producer_decision_references": len(producers),
                                            "unique_producer_requests": len({x["request_id"] for x in producers.values()})})}
    # Model measurements are immutable. Later source reviews get summarized by
    # summarize_audit; they cannot cause new draws or overwrite this checkpoint.
    frozen = output / "evaluation/summary.json"
    if frozen.exists():
        previous = _read(frozen)
        result["source_audit"] = previous["source_audit"]
    r.immutable(frozen, result)
    return result
