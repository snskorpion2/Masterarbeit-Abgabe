"""CPU admission of completed original tails, preserving A8 cell-local IDs.

No constructor, environment, provider or replay entry point exists here. Full
private A8 containers remain archives; only explicit active fields reach users.
"""
from contextlib import redirect_stderr, redirect_stdout
from copy import deepcopy
from hashlib import sha256
from io import BytesIO, StringIO
import json
from pathlib import Path
import re

import networkx as nx

from Experiments.fair_comparison_oct23_v1 import graph_contract as native
from Experiments.fair_comparison_oct23_v1 import baseline
from Experiments.fair_comparison_oct23_v1 import sdk_schema_cpu
from Experiments.fair_v2_oct24.A8 import project_subset as a8


ROOT = Path(__file__).resolve().parents[3]
G1 = ROOT / "Experiments/fair_v2_oct24/G1/freigabe_teil1.md"
G1_SHA = "c583169cd1ba2131325f82070b5145d6cab54fd92d96a6aef584c22efd5d930e"
PROTOCOL = "B3-completed-original-cell-binding-v1"
CELL_NAMESPACE = "B3-cell-identity-v1"
UNIT_NAMESPACE = "B3-global-native-unit-v1"
TAIL_PROTOCOL = "source-draw-confirmed-carrier-native-tail-worker:oct23-v1"
CANDIDATE = "AS_SCOPE_JOINT_ROW_V1"
WIRE = {"model": "deepseek.v3.2", "temperature": 0.7, "max_tokens": 8192, "stream": False}
ENDPOINT_SHA = sha256(b"https://bedrock-mantle.eu-north-1.api.aws/v1/chat/completions").hexdigest()


class BindingError(ValueError):
    """Fixed technical error only; never natural values or provider text."""


def _need(ok, code):
    if not ok:
        raise BindingError(code)


def pin(path):
    path = Path(path).absolute()
    _need(path.is_file() and not any(p.is_symlink() or getattr(p, "is_junction", lambda: False)()
                                   for p in (path, *path.parents)), "B3_REGULAR_FILE_REQUIRED")
    raw = path.read_bytes()
    return {"path": str(path.resolve()), "bytes": len(raw), "sha256": sha256(raw).hexdigest()}


def _pin_shape(value):
    _need(type(value) is dict and set(value) == {"path", "bytes", "sha256"}
          and type(value["path"]) is str and Path(value["path"]).is_absolute()
          and type(value["bytes"]) is int and value["bytes"] >= 0
          and type(value["sha256"]) is str and re.fullmatch(r"[a-f0-9]{64}", value["sha256"]),
          "B3_EXACT_PIN_REQUIRED")


def _read(record, proofs, *, parse=True):
    _pin_shape(record)
    _need(pin(record["path"]) == record, "B3_INPUT_PIN_CHANGED")
    proofs[record["path"]] = deepcopy(record)
    raw = Path(record["path"]).read_bytes()
    return native._strict_load(raw) if parse else raw


def _scope(source, arm, draw):
    _need(type(source) is str and bool(source.strip()), "B3_SOURCE_ID_REQUIRED")
    _need(arm in {"AS", "V1", CANDIDATE}, "B3_CANONICAL_ARM_REQUIRED")
    if type(draw) is int and draw in {1, 2, 3}:
        draw = "draw_" + str(draw)
    _need(type(draw) is str and draw in {"draw_1", "draw_2", "draw_3"}, "B3_DRAW_REQUIRED")
    return source, "AS" if arm == "AS" else "V1", draw


def cell_identity(source, arm, draw, rows_pin):
    source, arm, draw = _scope(source, arm, draw)
    _pin_shape(rows_pin)
    return "b3-cell-" + native.digest([CELL_NAMESPACE, source, arm, draw, rows_pin["sha256"]])


def _sidecar(bound, source, arm, draw, rows_pin, cell_id):
    rows = []
    for record in bound["records"]:
        rows.append({"unit_id": "b3-unit-" + native.digest([
            UNIT_NAMESPACE, source, arm, draw, rows_pin["sha256"], record["record_id"]]),
            "cell_id": cell_id, "source_id": source, "arm": arm, "draw_id": draw,
            "native_rows_sha256": rows_pin["sha256"], "native_record_id": record["record_id"],
            **{k: deepcopy(record[k]) for k in ("row_index", "native_field", "record_index",
                "category", "value_sha256", "source_sha256", "span_id", "span_sha256")}})
    _need(len({r["unit_id"] for r in rows}) == len(rows), "B3_GLOBAL_UNIT_COLLISION")
    return {"protocol": UNIT_NAMESPACE, "cell_id": cell_id, "rows_pin": deepcopy(rows_pin),
            "original_positions_frozen": True, "recompute_after_filtering": False, "units": rows}


def _receipts(result, proofs, *, native_object_count):
    receipts = result["physical_call_receipts"]
    _need(type(receipts) is list
          and type(result["physical_POSTs"]) is int and result["physical_POSTs"] == len(receipts)
          and type(result["unknown_executions"]) is int and result["unknown_executions"] == 0
          and type(result["unreceipted_runtime_entries"]) is int and result["unreceipted_runtime_entries"] == 0,
          "B3_COMPLETE_NATIVE_RECEIPTS_REQUIRED")
    _need(receipts or native_object_count == 0, "B3_ZERO_CALLS_REQUIRE_EMPTY_NATIVE_INVENTORY")
    identities = set()
    for wrapper in receipts:
        _need(wrapper["actual_wire_parameters"] == WIRE and wrapper["retries"] == 0
              and wrapper["phase"] == "concept_induction" and wrapper["status"] == "completed"
              and type(wrapper["POST_attempts"]) is int and wrapper["POST_attempts"] == 1
              and wrapper["unknown_execution"] is False, "B3_G1_WIRE_OR_DELIVERY_MISMATCH")
        receipt = _read(wrapper["actual_receipt"], proofs)
        _need(receipt == wrapper["native_receipt"], "B3_NATIVE_RECEIPT_COPY_MISMATCH")
        _need(wrapper["actual_receipt"]["path"] not in identities, "B3_DUPLICATE_PHYSICAL_RECEIPT")
        identities.add(wrapper["actual_receipt"]["path"])
        expected = {"POST_attempts": 1, "unknown_execution": False, "physical_dispatch_performed": True,
            "http_status": 200, "HTTP_body_complete": True, "text_completion_confirmed": True,
            "response_archive_complete": True, "raw_body_saved": True, "finish_reason": "stop",
            "error_class": None, "requested_model_alias": WIRE["model"],
            "expected_response_model": WIRE["model"], "provider_model": WIRE["model"],
            "model_matches_expected": True, "SDK_max_retries": 0, "requested_output_token_cap": 8192}
        _need(all(k in receipt and type(receipt[k]) is type(v) and receipt[k] == v
                  for k, v in expected.items()), "B3_NATIVE_DELIVERY_OR_MODEL_MISMATCH")
        native_root = Path(wrapper["actual_receipt"]["path"]).parents[2]
        condition = _read(pin(native_root / "condition.json"), proofs)
        expected_condition = {"endpoint_sha256": ENDPOINT_SHA, "model": WIRE["model"],
            "requested_model_alias": WIRE["model"], "expected_response_model": WIRE["model"],
            "SDK_max_retries": 0, "HTTP_timeout_seconds": 300, "max_physical_posts": 1}
        _need(all(condition.get(k) == v for k, v in expected_condition.items()),
              "B3_G1_MANTLE_ENDPOINT_OR_CONDITION_MISMATCH")
        actual = _read(wrapper["actual_request"], proofs, parse=False)
        declared = _read(wrapper["request"], proofs, parse=False)
        raw = _read(wrapper["raw_response"], proofs, parse=False)
        assistant = _read(wrapper["assistant"], proofs, parse=False)
        _need(actual == declared and sha256(actual).hexdigest() == receipt.get("wire_sha256")
              and sha256(raw).hexdigest() == receipt.get("response_sha256")
              and len(raw) == receipt.get("response_bytes"), "B3_ORIGINAL_WIRE_OR_RAW_BINDING_MISMATCH")
        payload, response = native._strict_load(actual), native._strict_load(raw)
        _need({k: v for k, v in payload.items() if k != "messages"} == WIRE,
              "B3_ACTUAL_PROVIDER_WIRE_MISMATCH")
        choices = response.get("choices")
        _need(response.get("model") == WIRE["model"] and type(choices) is list and len(choices) == 1
              and choices[0].get("finish_reason") == "stop"
              and type(choices[0].get("message", {}).get("content")) is str
              and choices[0]["message"]["content"].encode("utf8") == assistant,
              "B3_ORIGINAL_RAW_ASSISTANT_MISMATCH")
    roster = result["roster_evidence"]
    _need(roster.get("complete") is True and roster.get("multiset_equal") is True
          and type(roster["expected_calls"]) is int and type(roster["actual_calls"]) is int
          and roster["expected_calls"] == roster["actual_calls"] == len(receipts),
          "B3_COMPLETE_NATIVE_SCHEMA_ROSTER_REQUIRED")


def _graph_json(wrapped):
    graph = nx.MultiDiGraph(wrapped["value"])
    encoded = {"encoding": "B3-directed-multigraph-attributes-v1", "graph_attributes": deepcopy(graph.graph),
        "nodes": [{"node_id": node, "attributes": deepcopy(dict(attrs))} for node, attrs in graph.nodes(data=True)],
        "edges": [{"head": head, "tail": tail, "key": key, "attributes": deepcopy(dict(attrs))}
                  for head, tail, key, attrs in graph.edges(keys=True, data=True)]}
    return {**{k: deepcopy(v) for k, v in wrapped.items() if k != "value"},
            "value": encoded}


def _restore_graph(encoded):
    _need(encoded.get("encoding") == "B3-directed-multigraph-attributes-v1", "B3_GRAPH_ENCODING_REQUIRED")
    graph = nx.MultiDiGraph()
    graph.graph.update(deepcopy(encoded["graph_attributes"]))
    for node in encoded["nodes"]:
        graph.add_node(node["node_id"])
        graph.nodes[node["node_id"]].update(deepcopy(node["attributes"]))
    for edge in encoded["edges"]:
        graph.add_edge(edge["head"], edge["tail"], key=edge["key"])
        graph.edges[edge["head"], edge["tail"], edge["key"]].update(deepcopy(edge["attributes"]))
    return graph


def _save(path, value):
    raw = baseline.canonical(value)
    with Path(path).open("xb") as handle:
        handle.write(raw)
    return pin(path)


def bind_completed_cell(output_root, *, tail_plan_pin, worker_result_pin,
                        source, arm, draw, expected_rows_pin=None):
    """Archive a complete original A8 cell and globally scoped native sidecar.

    ``expected_rows_pin`` is the caller's frozen A8/constructor roster input.
    It is mandatory, so matching names cannot admit another native inventory.
    Rebinding an existing identity never overwrites or replays that cell.
    """
    try:
        source, arm, draw = _scope(source, arm, draw)
        _need(expected_rows_pin is not None, "B3_EXPECTED_ROWS_PIN_REQUIRED")
        proofs = {}
        approval = pin(G1)
        _need(approval["sha256"] == G1_SHA, "B3_G1_APPROVAL_CHANGED")
        _read(approval, proofs, parse=False)
        plan = _read(tail_plan_pin, proofs)
        result = _read(worker_result_pin, proofs)
        _need(plan["protocol"] == TAIL_PROTOCOL and result["protocol"] == TAIL_PROTOCOL
              and plan["plan_sha256"] == baseline.digest({k: v for k, v in plan.items() if k != "plan_sha256"})
              and result["plan_sha256"] == plan["plan_sha256"], "B3_TAIL_PLAN_BINDING_MISMATCH")
        native_arm = "AS" if arm == "AS" else CANDIDATE
        _need(all(v["case_id"] == source and v["system"] == native_arm and
                  type(v["draw_id"]) is int and "draw_" + str(v["draw_id"]) == draw
                  for v in (plan, result)), "B3_SOURCE_ARM_DRAW_MISMATCH")
        _need(result.get("complete") is True and result.get("failure") is None
              and result.get("extraction_invoked") is False and result.get("automatic_replay") is False,
              "B3_COMPLETED_ORIGINAL_TAIL_REQUIRED")
        policy = plan["execution_policy"]
        _need(policy["model"] == WIRE["model"] and policy["wire_parameters"] == WIRE
              and policy["timeout_seconds"] == 300 and policy["native_output_limit"] == 8192
              and policy["chunk_size"] == 8192 and policy["chunk_overlap"] == 0
              and policy["remove_doc_spaces"] is False and plan["transport_retries"] == 0,
              "B3_G1_CONSTRUCTION_CONDITION_MISMATCH")
        processing = plan["processing_config"]
        _need(all(processing.get(k) == v for k, v in {"filename_pattern": "source", "batch_size_concept": 64,
                  "include_concept": True, "total_shards_concept": 1, "current_shard_concept": 0}.items()),
              "B3_ORIGINAL_SCHEMA_SLOT_CONDITION_MISMATCH")
        _need(plan["rows_binding"] == expected_rows_pin, "B3_EXPECTED_INVENTORY_MISMATCH")
        rows = _read(expected_rows_pin, proofs)
        sources = [deepcopy(plan["source_chunk"])]
        _need(sources[0]["id"] == source, "B3_SOURCE_CHUNK_MISMATCH")
        for key in ("baseline_plan_binding", "source_manifest_binding", "runtime_binding", "worker_binding", "baseline_binding"):
            _read(plan[key], proofs, parse=False)
        for record in [*plan["producer_receipts"], *plan["code_bindings"]]:
            _read(record, proofs, parse=False)
        bound = native.bind_native_inventory(rows, sources)
        _receipts(result, proofs, native_object_count=len(bound["records"]))
        output = Path(plan["output_root"]).resolve()
        artifacts = {name: pin(output / suffix) for name, suffix in {
            "native_producer": "kg_extraction/source_native.jsonl", "original_graph": "kg_graphml/source_graph.graphml",
            "final_relation_csv": "concept_csv/triple_edges_source_from_json_with_concept.csv",
            "concept_node_csv": "concept_csv/concept_nodes_source_from_json_with_concept.csv",
            "concept_edge_csv": "concept_csv/concept_edges_source_from_json_with_concept.csv"}.items()}
        _need(result["native_graph"] == artifacts["original_graph"], "B3_ORIGINAL_GRAPH_PIN_MISMATCH")
        _read(result["native_result"], proofs, parse=False)
        kwargs = {}
        for name, record in artifacts.items():
            _read(record, proofs, parse=False)
            prefix = "native_producer_jsonl" if name == "native_producer" else name
            kwargs[prefix + "_path"], kwargs[prefix + "_sha256"] = record["path"], record["sha256"]
        cell_id = cell_identity(source, arm, draw, expected_rows_pin)
        target = Path(output_root).resolve() / "bound-cells" / cell_id
        _need(not any(p.is_symlink() or getattr(p, "is_junction", lambda: False)()
                      for p in (Path(output_root).absolute(), *Path(output_root).absolute().parents)),
              "B3_UNLINKED_OUTPUT_REQUIRED")
        _need(not target.is_relative_to(ROOT.resolve()), "B3_PRIVATE_ARCHIVE_REQUIRED")
        _need(not target.exists(), "B3_CELL_ALREADY_BOUND_OR_PARTIAL")
        with redirect_stdout(StringIO()), redirect_stderr(StringIO()):
            bridge = sdk_schema_cpu.build_sdk_schema_bindings(rows, sources, **kwargs)
            graph = nx.read_graphml(BytesIO(_read(artifacts["original_graph"], proofs, parse=False)), force_multigraph=True)
            inv, schema, wrapped = a8.bind_cell(bound, bridge, graph, cell_id=cell_id, export_kind="original")
            active = a8.active_cell({"inventory": inv, "schema": schema, "graph": wrapped})
        sidecar = _sidecar(bound, source, arm, draw, expected_rows_pin, cell_id)
        code = [pin(path) for path in (__file__, native.__file__, baseline.__file__, sdk_schema_cpu.__file__,
                                     sdk_schema_cpu.frozen.__file__, a8.__file__)]
        for record in [*bridge["code_pins"], *bridge["CPU_import_adapter"]["original_module_pins"]]:
            current = pin(record["path"])
            _need(current["sha256"] == record["sha256"], "B3_ORIGINAL_CONVERTER_CODE_CHANGED")
            if current not in code:
                code.append(current)
        for record in [*proofs.values(), *code]:
            _need(pin(record["path"]) == record, "B3_INPUT_CHANGED_DURING_CPU_BINDING")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.mkdir(exist_ok=False)
        active["graph"] = _graph_json(active["graph"])
        archives = {name: _save(target / (name + ".private.json"), value) for name, value in {
            "inventory": inv, "schema": schema, "graph": _graph_json(wrapped),
            "active_cell": active, "global_units": sidecar, "sdk_bridge": bridge}.items()}
        manifest = {"protocol": PROTOCOL, "cell_id": cell_id, "source_id": source, "arm": arm, "draw_id": draw,
            "rows_pin": expected_rows_pin, "tail_plan_pin": tail_plan_pin, "worker_result_pin": worker_result_pin,
            "G1_approval_pin": approval, "condition": WIRE, "endpoint_sha256": ENDPOINT_SHA,
            "source_pins": list(proofs.values()), "code_pins": code, "original_artifact_pins": artifacts,
            "archives": archives, "native_object_count": len(sidecar["units"]),
            "original_schema_POSTs": result["physical_POSTs"],
            "empty_native_inventory": len(sidecar["units"]) == 0,
            "zero_schema_call_endpoint": len(sidecar["units"]) == 0 and result["physical_POSTs"] == 0,
            "original_schema_assignments_frozen": True, "export_kind": "original",
            "new_extractions": 0, "new_model_calls": 0, "new_row_export_created": False,
            "technical_consistency_only": True, "semantic_quality_or_source_support_claimed": False}
        return _save(target / "manifest.private.json", manifest)
    except BindingError:
        raise
    except Exception:
        raise BindingError("B3_COMPLETED_CELL_BINDING_FAILED") from None


def load_bound_cell(manifest_pin):
    """Restore exactly the original A8 tuple for the existing CPU projector."""
    proofs = {}
    manifest = _read(manifest_pin, proofs)
    _need(manifest.get("protocol") == PROTOCOL, "B3_BOUND_CELL_PROTOCOL_REQUIRED")
    for record in [*manifest["source_pins"], *manifest["code_pins"], *manifest["archives"].values()]:
        _read(record, proofs, parse=False)
    inv = _read(manifest["archives"]["inventory"], proofs)
    schema = _read(manifest["archives"]["schema"], proofs)
    graph = _read(manifest["archives"]["graph"], proofs)
    graph["value"] = _restore_graph(graph["value"])
    return inv, schema, graph
