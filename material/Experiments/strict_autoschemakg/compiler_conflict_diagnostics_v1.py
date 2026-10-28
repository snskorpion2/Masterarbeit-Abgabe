"""Offline alternative conflict policy, not a change to the frozen compiler.

Only asserted order edges define exclusion dependencies. Date projections still
detect contradictions, but do not merge independent exclusion components.
Proofs are conditional on the explicitly recorded eligible premise subset.
Neither accepted bindings nor additional formal conclusions establish truth.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
import json
from pathlib import Path

from . import temporal_reasoner as reasoner
from . import temporal_compiler as compiler
from . import immutable_publish as pub
from .contract import sha256

POLICY = "asserted_dependency_conflict_isolation_v1"
ROOT = Path(__file__).resolve().parents[2]


def _nodes(primitive):
    if primitive.get("kind") == "event_time":
        return {primitive["event_id"]}
    pair = reasoner._order(primitive) if primitive.get("kind") in ("before", "after") else None
    return set(pair) if pair else set()


def _reachable(adjacency, start, target):
    pending, seen = [start], set()
    while pending:
        node = pending.pop()
        if node == target:
            return True
        if node not in seen:
            seen.add(node)
            pending.extend(adjacency.get(node, set()) - seen)
    return False


def _stable_result(primitives):
    return {key: value for key, value in reasoner.materialize(primitives).items()
            if key != "elapsed_seconds"}


def diagnose(primitives):
    """Compare policies without changing identities, bounds, bindings or rules.

    Unknown kinds remain inert, as in the original reasoner. This low-level
    function checks formal primitives only. The saved-artifact entrypoint also
    replays the unchanged compiler binding and raw-response audit first.
    """
    primitives = deepcopy(primitives)
    _, explicit, _, conflicts, _, _ = reasoner._prepare(primitives)
    nodes = set().union(*(_nodes(p) for p in primitives)) if primitives else set()
    adjacency = {node: set() for node in nodes}
    for a, b in explicit:
        adjacency[a].add(b)
        adjacency[b].add(a)
    components, unseen = [], set(nodes)
    while unseen:
        pending, component = [min(unseen)], set()
        while pending:
            node = pending.pop()
            if node not in component:
                component.add(node)
                pending.extend(adjacency[node] - component)
        unseen -= component
        components.append(component)
    components.sort(key=lambda component: sorted(component))
    bad = {node for conflict in conflicts if conflict["kind"] == "incompatible_bounds"
           for node in conflict["event_ids"]}
    excluded = [component for component in components if component & bad]
    blocked = set().union(*excluded) if excluded else set()
    remaining = [p for p in primitives if not _nodes(p) & blocked]
    # Remove invalid-time components before projecting dates. Their empty
    # interval intersections must not manufacture cycles through healthy nodes.
    _, orders, projected, _, _, _ = reasoner._prepare(remaining)
    directed = {}
    for a, b in set(orders) | set(projected):
        directed.setdefault(a, set()).add(b)
    cyclic_orders = sorted((a, b) for a, b in orders if _reachable(directed, b, a))
    cycle_nodes = {node for pair in cyclic_orders for node in pair}
    excluded.extend(component for component in components
                    if component & cycle_nodes and not component & blocked)
    excluded.sort(key=lambda component: sorted(component))
    blocked = set().union(*excluded) if excluded else set()
    eligible = [p for p in primitives if not _nodes(p) & blocked]
    alternative = _stable_result(eligible)
    if alternative["conflicts"] or alternative["excluded_components"]:
        raise ValueError("Residual conflict in eligible premises")
    proofs = {d["id"]: reasoner.verify_proof(d, eligible, alternative["derived"])
              for d in alternative["derived"]}
    if not all(proofs.values()):
        raise ValueError("Alternative conclusion failed unchanged proof verifier")
    original = _stable_result(primitives)
    return {"policy": POLICY, "logical_policy_change": True,
            "proof_scope": "eligible_primitives_only_not_original_full_premise_set",
            "input_primitives_sha256": reasoner._digest(primitives),
            "eligible_primitives_sha256": reasoner._digest(eligible),
            "eligible_primitives": eligible,
            "excluded_primitive_ids": sorted(p["id"] for p in primitives if _nodes(p) & blocked),
            "asserted_components": [sorted(c) for c in components],
            "excluded_asserted_components": [sorted(c) for c in excluded],
            "incompatible_time_nodes": sorted(bad),
            "cyclic_asserted_orders": [list(pair) for pair in cyclic_orders],
            "original": original, "alternative": alternative, "proofs": proofs}


def _same(left, right, message):
    if not pub.equal_json(left, right):
        raise ValueError(message)


def replay_bindings(schedule, results, event_index, saved, *, repaired, deterministic):
    """No additional repair or acceptance route beyond the frozen compiler."""
    with pub.publication_scope(True):
        if len(schedule) != len(results) or len({q["request_id"] for q in schedule}) != len(schedule):
            raise ValueError("Incomplete or duplicate compiler schedule")
        for request, record in zip(schedule, results):
            if record.get("request_id") != request["request_id"] or record.get("status") != "valid":
                raise ValueError("Incomplete compiler response")
            _same(compiler.classify(request, record["raw_response"]), record["parsed"],
                  "Parsed response differs from raw compiler response")
        replayed = compiler.project_primitives(schedule, results, event_index,
                                               repair_spans=repaired,
                                               deterministic_repairs=deterministic)
        _same(replayed, saved, "Frozen binding projection differs from replay")
        return replayed


def prepare(graph, output):
    """Read and audit one saved factorial compiler stage. Never initialize a model."""
    from . import completion_contracts as contracts, completion_pilot as stages

    graph, output = Path(graph).resolve(), Path(output).resolve()
    article = graph.parent.parent
    run = article.parent.parent
    if graph.parent.name != "graphs" or article.parent.name != "articles":
        raise ValueError("Expected a saved factorial graph directory")
    if output == run or output.is_relative_to(run) or run.is_relative_to(output):
        raise ValueError("Output must be isolated from the source run")
    stage = article / "stages" / (graph.name + "_compiler")
    source_paths = {run / "input_manifest.json", graph / "extraction.jsonl"}
    source_paths.update(path for folder in (stage, graph / "compiler")
                        for path in folder.rglob("*") if path.is_file())
    with pub.publication_scope(True):
        manifest = pub.read_json(run / "input_manifest.json")
        deterministic = "deterministic_repairs" in manifest
        if deterministic and (not isinstance(manifest["deterministic_repairs"], dict)
                or manifest["deterministic_repairs"].get("date_precision") != "supported_literal_only_v1"):
            raise ValueError("Unknown frozen date-precision repair policy")
        selected = [a for a in manifest["articles"] if a["slug"] == article.name]
        if len(selected) != 1 or article.name not in manifest["selected_article_slugs"]:
            raise ValueError("Graph article is not selected by the source manifest")
        source = Path(selected[0]["source_path"])
        if sha256(source) != selected[0]["source_sha256"]:
            raise ValueError("Source article changed")
        source_paths.add(source)
        before = {str(path): sha256(path) for path in sorted(source_paths)}
        # Pin every local implementation used by binding and raw replay. The
        # source manifest is evidence, not permission to execute changed code.
        names = ("temporal_compiler", "temporal_reasoner", "completion_contracts",
                 "completion_pilot", "reliability_v2", "contract", "extended_artifacts",
                 "recall_methods", "technical_repairs", "local_runtime", "immutable_publish")
        code = {}
        for name in names:
            path = Path(__file__).with_name(name + ".py")
            key = path.relative_to(ROOT).as_posix()
            code[key] = sha256(path)
            if manifest["code_hashes"].get(key) != code[key]:
                raise ValueError("Frozen replay implementation changed: " + key)
        code[Path(__file__).resolve().relative_to(ROOT).as_posix()] = sha256(Path(__file__))
        inputs = contracts.load_inputs(source, graph / "extraction.jsonl")
        contract = pub.read_json(stage / "schedule.json")
        schedule = contract["requests"]
        expected = compiler.formalization_requests(inputs["items"], inputs["event_index"],
                                                   contract_version="v2")
        if len(schedule) != len(expected):
            raise ValueError("Compiler schedule does not cover this native graph")
        for request, reference in zip(schedule, expected):
            for key in ("kind", "item_ids", "items", "event_index", "prompt", "contract_version"):
                _same(request[key], reference[key], "Compiler input identity changed: " + key)
        stages._audit_stage(stage, schedule, contract["protocol_id"], compiler.schema_for,
                            compiler.classify, variant=contract["variant"], model=contract["model"],
                            context=contract["context_tokens"])
        results = pub.read_json(stage / "final_responses.json")
        reports = {}
        for label, repaired in (("strict", False), ("repaired", True)):
            saved = pub.read_json(graph / "compiler" / ("projection_" + label + ".json"))
            projection = replay_bindings(schedule, results, inputs["event_index"], saved,
                                         repaired=repaired, deterministic=deterministic)
            report = diagnose(projection["primitives"])
            old = pub.read_json(graph / "compiler/reasoning" / label / "result.json")
            _same(report["original"], {k: v for k, v in old.items() if k != "elapsed_seconds"},
                  "Original whole-component result changed")
            reports[label] = report
        if before != {str(path): sha256(path) for path in sorted(source_paths)}:
            raise ValueError("Source artifacts changed during replay")
        audit = {"policy": POLICY, "source_graph": str(graph), "output": str(output),
                 "input_hashes": before, "code_hashes": code, "new_model_calls": 0,
                 "source_artifacts_modified": False, "rule_version": reasoner.RULE_VERSION,
                 "limitations": ["Alternative logical exclusion policy, not a core bug fix",
                     "Binding and proofs do not certify source truth or quality improvement",
                     "Existing compiler cost belongs to the source run and is not zero",
                     "No F1 change, no new model sampling, no event splitting or span relaxation"]}
        summary = {"policy": POLICY, "status": "complete", "new_model_calls": 0,
                   "projections": {label: {
                       "input_primitives": len(report["eligible_primitives"]) + len(report["excluded_primitive_ids"]),
                       "eligible_primitives": len(report["eligible_primitives"]),
                       "excluded_events": sum(map(len, report["excluded_asserted_components"])),
                       "original_derived": len(report["original"]["derived"]),
                       "original_conflicts": len(report["original"]["conflicts"]),
                       "alternative_derived": len(report["alternative"]["derived"]),
                       "alternative_conflicts": len(report["alternative"]["conflicts"]),
                       "verified_proofs": sum(report["proofs"].values())}
                       for label, report in reports.items()}, "limitations": audit["limitations"]}
        return audit, reports, summary


def execute(graph, output):
    output = Path(output).resolve()
    if output.exists():
        raise ValueError("Diagnostic output already exists, never overwrite")
    audit, reports, summary = prepare(graph, output)
    if (any(sha256(Path(path)) != digest for path, digest in audit["input_hashes"].items())
            or any(sha256(ROOT / path) != digest for path, digest in audit["code_hashes"].items())):
        raise ValueError("Inputs or code changed before diagnostic publication")
    output.mkdir(parents=True, exist_ok=False)
    with pub.publication_scope(True):
        pub.publish_json(output / "input_manifest.json", audit)
        for label, report in reports.items():
            pub.publish_json(output / (label + ".json"), report)
        pub.publish_json(output / "summary.json", summary)
    return summary


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--graph", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--execute", action="store_true", help="Write a new isolated offline diagnostic")
    args = parser.parse_args(argv)
    result = execute(args.graph, args.output) if args.execute else prepare(args.graph, args.output)[2]
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
