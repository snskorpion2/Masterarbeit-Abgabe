"""Pinned original SDK CSV/graph -> explicit occurrence-schema bindings.

CPU replay qualifies the actual producer order and complete final graph pack.
Per-row relation concepts remain separate. Existing lexical node-concept pools
are inherited as technical assignments to their native slots, not repaired or
certified occurrence types. No graph, native inventory or original is changed.
"""
from __future__ import annotations

from collections import Counter
from contextlib import redirect_stdout
from copy import deepcopy
import csv
from hashlib import sha256
from io import BytesIO, StringIO
import json
from pathlib import Path
import socket
from tempfile import TemporaryDirectory
from unittest.mock import patch

import networkx as nx

from Experiments.fair_comparison_oct23_v1 import graph_contract as contract
from Experiments.strict_autoschemakg import contract as native_contract
from Experiments.strict_autoschemakg.source_imports import verified_source_imports
from Tools.experiments.as_parallel_export_oct20_v1 import export_control

VERSION = "producer-position-bound-original-SDK-schema-bridge:oct23-v1"


def _require(condition, message):
    if not condition:
        raise ValueError(message)


def _pin(path, expected):
    path = Path(path).resolve()
    raw = path.read_bytes()
    _require(sha256(raw).hexdigest() == expected, "Bound original artifact SHA mismatch: " + str(path))
    return raw, {"path": str(path), "sha256": expected, "bytes": len(raw)}


def _csv(raw):
    reader = csv.DictReader(StringIO(raw.decode("utf-8-sig"), newline=""))
    fields = reader.fieldnames
    _require(fields and len(set(fields)) == len(fields), "Unique CSV field headers required")
    rows = list(reader)
    _require(all(set(row) == set(fields) and all(type(v) is str for v in row.values()) for row in rows),
             "Complete original CSV field strings required")
    return rows


def _file_csv(path):
    return _csv(Path(path).read_bytes())


def _native_projection_positions(records, clean_text):
    # This is the d0a1666 original json2csv write-block order, not the input
    # inventory's EE/EV/VV order. The full actual replay below must agree with
    # every emitted position. Identical payloads retain their distinct indices.
    order = {"EE": 0, "VV": 1, "EV": 2}
    result = []
    for record in sorted(records, key=lambda r: (r["row_index"], order[r["category"]], r["record_index"])):
        value = record["value"]
        if record["category"] == "EV":
            projections = [(value["Event"], "is participated by", entity) for entity in value["Entity"]]
        else:
            projections = [(value["Head"], value["Relation"], value["Tail"])]
        for index, triple in enumerate(projections):
            cleaned = [clean_text(part) for part in triple]
            _require(all(cleaned), "Native projection lacks complete original-export coverage")
            result.append({"record": record, "projection_index": index, "triple": cleaned})
    return result


def build_sdk_schema_bindings(native_rows, sources, *, native_producer_jsonl_path,
                              native_producer_jsonl_sha256, original_graph_path, original_graph_sha256,
                              final_relation_csv_path, final_relation_csv_sha256,
                              concept_node_csv_path, concept_node_csv_sha256,
                              concept_edge_csv_path, concept_edge_csv_sha256, row_bindings=None):
    """Replay the pinned producer and bind final rows/actual concepts to slots.

    The complete single producer JSONL must equal native_rows in original order.
    A fresh verified original-SDK import context is required, so use this from a
    separate CPU orchestration process, outside an already imported SDK worker.
    Final CSV order, full triples and inherited synsets must match the actual
    original converter output. Re-exporting that output with the supplied final
    concept CSV pack must exactly reproduce every original graph node and edge.
    Missing coverage, unknown order and detached concepts fail closed.
    """
    declarations = {
        "native_producer": (native_producer_jsonl_path, native_producer_jsonl_sha256),
        "original_graph": (original_graph_path, original_graph_sha256),
        "final_relation_csv": (final_relation_csv_path, final_relation_csv_sha256),
        "concept_node_csv": (concept_node_csv_path, concept_node_csv_sha256),
        "concept_edge_csv": (concept_edge_csv_path, concept_edge_csv_sha256),
    }
    originals, pins = {}, {}
    for name, (path, expected) in declarations.items():
        originals[name], pins[name] = _pin(path, expected)
    producer_rows = [contract._strict_load(line) for line in originals["native_producer"].decode("utf-8-sig").splitlines() if line.strip()]
    _require(producer_rows == native_rows, "Complete bound producer rows/order differ from supplied native inventory")
    _require(all(contract.SDK_EV in row and contract.EV not in row for row in producer_rows), "Actual original SDK producer fields required")
    bound = contract.bind_native_inventory(native_rows, sources, row_bindings=row_bindings)
    original_graph = nx.read_graphml(BytesIO(originals["original_graph"]), force_multigraph=True)
    _require(original_graph.is_directed(), "Original directed GraphML required")
    final_rows = _csv(originals["final_relation_csv"])
    required_relation = {":START_ID", ":END_ID", "relation", "concepts", "synsets", ":TYPE"}
    _require(all(required_relation <= set(row) and row[":TYPE"] == "Relation" for row in final_rows), "Complete final native Relation CSV required")
    concept_node_rows, concept_edge_rows = _csv(originals["concept_node_csv"]), _csv(originals["concept_edge_csv"])
    _require(all({"concept_id:ID", "name", ":LABEL"} <= set(row) for row in concept_node_rows), "Original concept node CSV required")
    _require(all({":START_ID", ":END_ID", "relation", ":TYPE"} <= set(row) and row[":TYPE"] == "Concept" for row in concept_edge_rows), "Original concept edge CSV required")
    source_paths = [Path(__file__), Path(export_control.__file__), Path(native_contract.__file__),
                    native_contract.DEFAULT_SOURCE / "atlas_rag/kg_construction/utils/json_processing/json_to_csv.py",
                    native_contract.DEFAULT_SOURCE / "atlas_rag/kg_construction/utils/csv_processing/csv_to_graphml.py",
                    native_contract.DEFAULT_SOURCE / "atlas_rag/kg_construction/concept_to_csv.py"]
    source_pins = [{"path": str(path.resolve()), "sha256": sha256(path.read_bytes()).hexdigest()} for path in source_paths]
    def no_network(*args, **kwargs):
        raise AssertionError("Original CSV/schema CPU replay may not access the network")
    with patch.object(socket.socket, "connect", no_network), patch.object(socket, "create_connection", no_network):
        with verified_source_imports(native_contract.DEFAULT_SOURCE):
            from atlas_rag.kg_construction.utils.json_processing import json_to_csv as native_csv
            from atlas_rag.kg_construction.utils.csv_processing import csv_to_graphml as native_graph
            from atlas_rag.llm_generator.format.validate_json_schema import ATLAS_SCHEMA
            positions = _native_projection_positions(bound["records"], native_csv.clean_text)
            with TemporaryDirectory(prefix="bound-AS-schema-replay-") as temporary:
                temp = Path(temporary)
                (temp / "input").mkdir()
                (temp / "input/bound_native.jsonl").write_bytes(originals["native_producer"])
                with redirect_stdout(StringIO()):
                    native_csv.json2csv("bound", str(temp / "input"), str(temp / "csv"), ATLAS_SCHEMA, False)
                replay_rows = _file_csv(temp / "csv/triple_edges_bound_from_json_without_emb.csv")
                _require(len(positions) == len(replay_rows) == len(final_rows), "Native/final CSV relation coverage differs from full original replay")
                relation_bindings, relation_audit = [], []
                for ordinal, (position, replay, final) in enumerate(zip(positions, replay_rows, final_rows), 1):
                    expected = [*position["triple"], "Relation"]
                    replay_values = [replay[k] for k in (":START_ID", "relation", ":END_ID", ":TYPE")]
                    final_values = [final[k] for k in (":START_ID", "relation", ":END_ID", ":TYPE")]
                    _require(expected == replay_values == final_values and replay["synsets"] == final["synsets"],
                             "Native/final CSV position or whole triple/synsets differs from original replay")
                    record = position["record"]
                    attrs = {"native_csv_record": str(ordinal), "native_csv_row_json": json.dumps(final, ensure_ascii=True)}
                    encoded = export_control.original_row_concepts(final["concepts"])
                    if encoded is not None:
                        attrs["concepts"] = encoded
                    if final["synsets"] != "":
                        attrs["native_csv_synsets"] = final["synsets"]
                    relation_bindings.append({"record_id": record["record_id"], "projection_index": position["projection_index"], "attributes": attrs})
                    relation_audit.append({"final_csv_ordinal": ordinal, "record_id": record["record_id"],
                        "native_category": record["category"], "projection_index": position["projection_index"],
                        "row_index": record["row_index"], "source_id": record["source_id"], "span_id": record["span_id"],
                        "source_sha256": record["source_sha256"], "native_field": record["native_field"],
                        "record_index": record["record_index"], "exact_original_cleaned_triple": position["triple"]})
                replay_node_rows = _file_csv(temp / "csv/triple_nodes_bound_from_json_without_emb.csv")
                for name, filename in (("final_relation_csv", "final.csv"), ("concept_node_csv", "concept_nodes.csv"), ("concept_edge_csv", "concept_edges.csv")):
                    (temp / filename).write_bytes(originals[name])
                with redirect_stdout(StringIO()):
                    native_graph.csvs_to_graphml(str(temp / "csv/triple_nodes_bound_from_json_without_emb.csv"),
                        str(temp / "csv/text_nodes_bound_from_json.csv"), str(temp / "final.csv"),
                        str(temp / "csv/text_edges_bound_from_json.csv"), str(temp / "concept_nodes.csv"),
                        str(temp / "concept_edges.csv"), str(temp / "replayed.graphml"), True)
                replayed_graph = nx.read_graphml(temp / "replayed.graphml", force_multigraph=True)
                _require(contract._graph_snapshot(original_graph) == contract._graph_snapshot(replayed_graph),
                         "Original final graph differs from complete actual SDK CSV replay")
            original_node_by_label = {}
            for row in replay_node_rows:
                key = native_graph.get_node_id(row["name:ID"], {})
                _require(key in original_graph and original_graph.nodes[key].get("id") == native_graph.sanitize_xml_string(row["name:ID"])
                         and original_graph.nodes[key].get("type") == row["type"], "Original replay endpoint-ID/type binding differs")
                _require(row["name:ID"] not in original_node_by_label, "Ambiguous original CSV node label")
                original_node_by_label[row["name:ID"]] = key
            slot_rows = []
            for record in bound["records"]:
                value = record["value"]
                slots = [("/Event", value["Event"])] + [("/Entity/" + str(i), label) for i, label in enumerate(value["Entity"])] if record["category"] == "EV" else [("/Head", value["Head"]), ("/Tail", value["Tail"])]
                for path, label in slots:
                    cleaned = native_csv.clean_text(label)
                    original_key = original_node_by_label.get(cleaned)
                    slot_rows.append({"record_id": record["record_id"], "field_path": path,
                        "original_node_id": original_key, "original_cleaned_label": cleaned,
                        "native_pointer": "/native_rows/" + str(record["row_index"]) + "/" + record["native_field"] + "/" + str(record["record_index"]) + path,
                        "source_id": record["source_id"], "source_sha256": record["source_sha256"], "span_id": record["span_id"]})
    concept_bindings, represented_edges, represented_nodes = [], set(), set()
    original_concept_edges = [(u, v, key, attrs) for u, v, key, attrs in original_graph.edges(keys=True, data=True) if attrs.get("type") == "Concept"]
    for slot in slot_rows:
        if slot["original_node_id"] is None:
            continue
        for head, tail, key, attrs in original_concept_edges:
            if head != slot["original_node_id"]:
                continue
            _require(original_graph.nodes[tail].get("type") == "concept", "Original Concept edge target is not a concept node")
            concept_bindings.append({"record_id": slot["record_id"], "field_path": slot["field_path"],
                "node_key": str(tail), "node_attributes": deepcopy(dict(original_graph.nodes[tail])),
                "edge_attributes": deepcopy(dict(attrs))})
            represented_edges.add((head, tail, key)); represented_nodes.add(tail)
    all_concept_nodes = {node for node, attrs in original_graph.nodes(data=True) if attrs.get("type") == "concept"}
    _require(len(represented_edges) == len(original_concept_edges) and represented_nodes == all_concept_nodes,
             "Original concept graph has incomplete native-slot coverage or detached concepts")
    pool_counts = Counter(slot["original_node_id"] for slot in slot_rows if slot["original_node_id"] is not None)
    pool_rows = [{"original_node_id": str(node), "original_node_type": original_graph.nodes[node]["type"],
                  "original_display_label": original_graph.nodes[node]["id"],
                  "native_slots_inheriting_original_pool": count,
                  "semantic_assignment_certified": False} for node, count in sorted(pool_counts.items())]
    for name, (path, expected) in declarations.items():
        _require(_pin(path, expected)[0] == originals[name], "Original artifact changed during schema bridge")
    _require(source_pins == [{"path": str(path.resolve()), "sha256": sha256(path.read_bytes()).hexdigest()} for path in source_paths],
             "SDK schema bridge implementation changed during replay")
    schema = {"protocol": VERSION, "original_artifact_pins": pins,
              "original_concept_node_CSV_rows": concept_node_rows, "original_concept_edge_CSV_rows": concept_edge_rows,
              "original_final_relation_CSV_rows": final_rows,
              "assignment_meaning": "Inherited original technical lexical node-concept pools; not verified occurrence types, identity or a schema repair",
              "original_node_pools": pool_rows}
    return {"protocol": VERSION, "relation_bindings": relation_bindings, "concept_bindings": concept_bindings,
            "schema": schema, "pins": pins, "code_pins": source_pins,
            "native_sha256": bound["native_sha256"], "source_manifest_sha256": bound["source_manifest_sha256"],
            "audit": {"original_final_graph_replay_equal": True, "original_SDK_commit": native_contract.PIN,
                      "producer_rows_equal_in_order": True, "native_projected_slots": len(positions),
                      "final_relation_rows": len(final_rows), "relation_rows": relation_audit,
                      "original_concept_nodes": len(all_concept_nodes), "original_concept_edges": len(original_concept_edges),
                      "original_concept_nodes_unrepresented": 0, "original_concept_edges_unrepresented": 0,
                      "native_slot_concept_bindings": len(concept_bindings), "native_slot_rows": slot_rows,
                      "original_node_pools": pool_rows,
                      "native_slots_not_emitted_by_original_converter": sum(slot["original_node_id"] is None for slot in slot_rows),
                      "parallel_concept_copies_may_exceed_original_edge_count": True},
            "new_model_calls": 0, "semantic_schema_repaired": False,
            "same_bindings_required_in_both_event_policies": True,
            "boundary": "Actual original single-producer CSV order and complete final graph replay, with per-row concepts and inherited node-concept memberships. No semantic schema correction, source truth, referent identity or QA gain certified."}
