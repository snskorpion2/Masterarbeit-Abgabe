"""CPU-only constructed input-contract probe of original graph edge retention.

This is not an extraction experiment or an overall ladder stage admission.
Original node IDs and attributes are copied unchanged. The derivative changes
only relation-row retention and records row-level category/source provenance.
"""
from __future__ import annotations

import argparse
from collections import Counter
from contextlib import redirect_stdout
import csv
import hashlib
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "Experiments/src"))

import networkx as nx
from graphml_export import add_graph_edge_once, write_graphml_preserving_text
from Experiments.strict_autoschemakg.source_imports import verified_source_imports

ORIGINAL = ROOT / "Tools/ReferenceRepos/benchmark_autoschemakg_original"
FIELDS = ("head", "tail", "relation", "type", "category", "source_sha256", "record_id")
CLAIM_LIMIT = (
    "Constructed CPU input-contract countercases only. No model generation, "
    "benchmark score, independently annotated source truth or overall ladder "
    "stage admission. Original node identity/type behavior remains unchanged."
)


def save_json(path: Path, value) -> None:
    with path.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.write("\n")


def write_csv(path: Path, header, rows) -> None:
    with path.open("x", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(header)
        writer.writerows(rows)


def fixture(case_id: str, source: str, relations: list[str]) -> dict:
    source_hash = hashlib.sha256(source.encode("utf-8")).hexdigest()
    return {
        "case_id": case_id,
        "source": source,
        "source_sha256": source_hash,
        "input_kind": "constructed_component_countercase",
        "rows": [
            {"head": "Mira", "tail": "Solis", "relation": relation,
             "type": "Relation", "category": "EE", "source_sha256": source_hash,
             "record_id": f"{case_id}:row:{index}"}
            for index, relation in enumerate(relations)
        ],
    }


def countercases() -> list[dict]:
    cases = [
        fixture("one_relation", "Mira founded Solis.", ["founded"]),
        fixture("parallel_relations", "Mira founded and manages Solis.",
                ["founded", "manages"]),
        fixture("duplicate_occurrences",
                "Mira founded Solis. Mira founded Solis. Mira manages Solis.",
                ["founded", "founded", "manages"]),
    ]
    identical = fixture("identical_input_rows", "Mira founded Solis.",
                        ["founded", "founded"])
    identical["rows"][1]["record_id"] = identical["rows"][0]["record_id"]
    cases.append(identical)
    return cases


def relation_rows(graph: nx.Graph) -> list[dict]:
    return [
        {"head": graph.nodes[u]["id"], "tail": graph.nodes[v]["id"], **attrs}
        for u, v, attrs in graph.edges(data=True)
        if attrs.get("type") == "Relation"
    ]


def row_multiset(rows: list[dict]) -> Counter:
    return Counter(tuple(row.get(field) for field in FIELDS) for row in rows)


def preserve_relation_rows(original_graph, rows, node_id) -> nx.MultiDiGraph:
    """Reuse existing edge/text helpers and leave every original node unchanged."""
    graph = nx.MultiDiGraph()
    graph.add_nodes_from((key, dict(attrs)) for key, attrs in original_graph.nodes(data=True))
    for index, row in enumerate(rows):
        start, end = node_id(row["head"]), node_id(row["tail"])
        if start not in graph or end not in graph:
            raise ValueError("The isolated edge probe requires existing original nodes")
        add_graph_edge_once(
            graph, start, end, f"input-row:{index}:{row['record_id']}",
            **{field: row[field] for field in FIELDS if field not in {"head", "tail"}},
        )
    for index, (start, end, attrs) in enumerate(original_graph.edges(data=True)):
        if attrs.get("type") != "Relation":
            add_graph_edge_once(graph, start, end, f"original-auxiliary:{index}", **attrs)
    return graph


def run_case(folder: Path, case: dict, native) -> dict:
    folder.mkdir()
    save_json(folder / "fixture.json", case)
    (folder / "constructed-source.txt").write_text(case["source"], encoding="utf-8")
    rows = case["rows"]
    source_id = hashlib.sha256((case["source"] + "_text").encode("utf-8")).hexdigest()
    # The text-node ID is an opaque identity shared by both builders. It is not
    # interpreted as independently extracted or annotated source evidence.
    write_csv(folder / "nodes.csv", ["name:ID", "type", "concepts", "synsets", ":LABEL"],
              [[label, "entity", "[]", "[]", "Node"] for label in ("Mira", "Solis")])
    write_csv(folder / "text.csv", ["text_id:ID", "original_text", ":LABEL"],
              [[source_id, case["source"], "Text"]])
    write_csv(folder / "relations.csv",
              [":START_ID", ":END_ID", "relation", "concepts", "synsets", ":TYPE",
               "category", "source_sha256", "record_id"],
              [[row["head"], row["tail"], row["relation"], "[]", "[]", row["type"],
                row["category"], row["source_sha256"], row["record_id"]] for row in rows])
    write_csv(folder / "text_edges.csv", [":START_ID", ":END_ID", "relation", ":TYPE"],
              [[label, source_id, "Source", "Source"] for label in ("Mira", "Solis")])
    original_file, candidate_file = folder / "original.graphml", folder / "lossless.graphml"
    began = time.perf_counter()
    with (folder / "original.stdout.txt").open("x", encoding="utf-8") as log, redirect_stdout(log):
        native.csvs_to_graphml(
            str(folder / "nodes.csv"), str(folder / "text.csv"),
            str(folder / "relations.csv"), str(folder / "text_edges.csv"),
            output_file=str(original_file), include_concept=False,
        )
    original_seconds = time.perf_counter() - began
    original_graph = nx.read_graphml(original_file, force_multigraph=True)
    began = time.perf_counter()
    candidate_graph = preserve_relation_rows(original_graph, rows, native.get_node_id)
    write_graphml_preserving_text(candidate_graph, candidate_file)
    candidate_seconds = time.perf_counter() - began
    # Verify the serialized artifact, not just the in-memory graph.
    reloaded = nx.read_graphml(candidate_file, force_multigraph=True)
    original_rows, candidate_rows = relation_rows(original_graph), relation_rows(reloaded)
    all_rows_retained = row_multiset(rows) == row_multiset(candidate_rows)
    nodes_unchanged = dict(original_graph.nodes(data=True)) == dict(reloaded.nodes(data=True))
    auxiliary = lambda graph: Counter(
        (u, v, json.dumps(attrs, sort_keys=True)) for u, v, attrs in graph.edges(data=True)
        if attrs.get("type") != "Relation"
    )
    auxiliary_unchanged = auxiliary(original_graph) == auxiliary(reloaded)
    expected_original_count = 1
    if len(original_rows) != expected_original_count:
        raise AssertionError("Original countercase differs from the reproduced pair-based retention rule")
    if not (all_rows_retained and nodes_unchanged and auxiliary_unchanged):
        raise AssertionError("Lossless graph roundtrip changed or lost input records/nodes/source edges")
    result = {
        "case_id": case["case_id"], "input_kind": case["input_kind"],
        "input_relation_records": len(rows), "distinct_relation_labels": len({r["relation"] for r in rows}),
        "original_exported_relation_records": len(original_rows),
        "original_retained_labels": [r["relation"] for r in original_rows],
        "original_relation_record_retention": len(original_rows) / len(rows),
        "lossless_exported_relation_records": len(candidate_rows),
        "lossless_relation_record_retention": len(candidate_rows) / len(rows),
        "serialized_complete_row_multiset_equal": all_rows_retained,
        "serialized_original_node_ids_types_attributes_unchanged": nodes_unchanged,
        "serialized_auxiliary_edges_unchanged": auxiliary_unchanged,
        "original_seconds": original_seconds, "lossless_seconds": candidate_seconds,
        "runtime_claim": "tiny CPU intervals descriptive only; not a speed advantage claim",
        "extra_model_calls": 0, "claim_limit": CLAIM_LIMIT,
    }
    save_json(folder / "comparison.json", result)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    intended = (ROOT / "Experiments/results/autoschema_ladder_oct14_v1/graph_component").resolve()
    if output != intended and intended not in output.parents:
        raise ValueError("Output must stay in the owned graph_component directory")
    output.mkdir(parents=True, exist_ok=False)
    bindings = {
        str(path.relative_to(ROOT)).replace("\\", "/"): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in (
            Path(__file__), ROOT / "Experiments/src/graphml_export.py",
            ROOT / "Experiments/src/triple_utils.py",
            ORIGINAL / "atlas_rag/kg_construction/utils/csv_processing/csv_to_graphml.py",
        )
    }
    with verified_source_imports(ORIGINAL):
        from atlas_rag.kg_construction.utils.csv_processing import csv_to_graphml as native
        results = [run_case(output / case["case_id"], case, native) for case in countercases()]
    summary = {
        "protocol": "autoschema-ladder-graph-component-cpu:v1",
        "original_function": "atlas_rag.kg_construction.utils.csv_processing.csv_to_graphml.csvs_to_graphml",
        "intervention": "relation-row-preserving MultiDiGraph using existing edge/write helpers",
        "code_bindings": bindings, "cases": results,
        "all_countercases_preserve_100_percent_of_input_relation_records": all(
            result["serialized_complete_row_multiset_equal"] for result in results),
        "original_parallel_relation_loss_reproduced": results[1]["original_exported_relation_records"] == 1,
        "fresh_model_calls": 0, "semantic_extraction_quality_measured": False,
        "overall_ladder_stage_admitted": False, "claim_limit": CLAIM_LIMIT,
    }
    save_json(output / "summary.json", summary)
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    main()
