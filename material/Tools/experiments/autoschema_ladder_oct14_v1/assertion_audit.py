"""Offline artifact audit for the separately identified assertion construction fork.

No provider, credential, embedding or judge imports. Exact span/IR/graph/receipt
checks certify transport preservation only; private source reviews own semantics.
"""
from __future__ import annotations

import argparse
import ast
from collections import Counter
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
import tempfile

ROOT = Path(__file__).resolve().parents[3]
TOOLS = ROOT / "Tools/experiments/autoschema_ladder_oct14_v1"
RESULTS = ROOT / "Experiments/results/autoschema_ladder_oct14_v1"
PROTOCOL = "source-assertion-autonomous-construction:oct14-v1"
AUDIT_PROTOCOL = "source-assertion-artifact-audit:oct14-v1"
APPROVED_SCRIPT = {"0bd3ee4cf3c4b188e709f1bb1def59f0bfe2d4f523bced96d0aaac76eace1970",
                   "6af81e4a5f5161076cab9e73815f52f069188cc7a905117aad501ff8040f6a01"}
APPROVED_CONTRACT = {"636c11684bbaa7939e32b16de46c707e15b5512224e9463b3a0a36b6f4c2a554",
                     "c4f5d305bbde51f31ed1c8d3f34f8760ffee04a28ddbd0de5756807c3aefbb86",
                     "730c8d0c2c406cd50ad290ed58d24c807d0df4be14839e4eb06cd00cc7954960"}
PARAMETER_INTENT_SHA = "76569fa0f3273a9147023bed3f30471f0d3148854ce3978f404c9730e46e7a26"
SOURCE_FILES = {
    "fixtures.json": "49f685e444c2c407baff0a0efb0c4dc22bf109501d1f14e9ed40a4ee8d5a0c59",
    "fixtures_temporal_controls_root_v1.json": "92b5aa68a469bf3e1857af5205ca11a1ccb49c62782e2eb86baa5b247a666856",
    "fixtures_causal_controls_v2.json": "e8d393754204544bfd9aa747bdf66219c859a0775a164a068e8f48b0c6c4c73b",
    "fixtures_static_recall_control_v1.json": "4dd48b74efe9dee71ccb08516348c2b50bc112083f6248eb79aea2273a2afa5f",
    "fixtures_shared_referent_control_v1.json": "63975167c758e4a1a25abbb6e2a2574d89aa1a5690e9e195b99c5a4cb9f536f5",
    "fixtures_unary_smile_control_v1.json": "c9605cd70add4f43bd431a676b0b268cfaf1cb1fe16317541b0b8726b2723161",
    "fixtures_assertion_ir_countercontrols_v2.json": "789a9706ea3461ecef928f8c2d2df8bb01573dee00dac8f8cc53eb8309d2191a",
    "fixtures_assertion_ir_zeroarity_v3.json": "b64c6bd103c3a8a086792a5a59aa31a1e33c3ffa755ecca2397ddce615ee1049",
    "fixtures_assertion_ir_s0_regression_v3.json": "beb5eee716cdffb9436c1a89d97e2a107efd63dfa01360aa75137c250fbfac81",
}
RUNTIME_PINS = {
    "Tools/experiments/autoschema_ladder_oct14_v1/runner.py": "e0eede21fe64e14605e3498538260329b6bf5fd24ae9f80e0fb57fb1e5ef434a",
    "Tools/abschluss/run_benchie_semantic_hawki_oct13_v1.py": "95426f7f0ea696d79be2d37f2c99e16356459a3f77c4dfd067efb3ca72925d94",
    "Tools/hawki/probe.py": "b26967262c438dc8c0aca8b8e22589f4f0b9a9e42a9ef2335c9d9c822679d1f1",
    "Tools/hawki/evaluation_controls_v2.py": "e35a253f0b9648cf0c90fcfe13900925a5aea7ad9e3a992bf95b447b0383e79b",
    "Experiments/strict_autoschemakg/contract.py": "cc634df3e0daad84b6b921cf29d68b6b391cce4e0105ef3d4acb2fb00b33bfad",
    "Experiments/strict_autoschemakg/source_imports.py": "1808b7acf92354b3c9b3d248a2db0ed84d81b08a891bf99f9785980286a46f8e",
}
PURE_NAMES = {"fields", "nonempty", "source_span", "decode_ir", "json_text",
              "build_graph", "recover_graph", "graph_signature", "legacy_views", "messages"}


def require(condition, reason):
    if not condition:
        raise ValueError(reason)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def strict(raw):
    def pairs(items):
        value = {}
        for key, item in items:
            require(key not in value, "Duplicate JSON key")
            value[key] = item
        return value

    def invalid(_):
        raise ValueError("Nonfinite JSON")

    return json.loads(raw, object_pairs_hook=pairs, parse_constant=invalid)


def read(path):
    return strict(path.read_bytes())


def pure_source(raw):
    """Compile only reviewed pure functions, never producer imports or main."""
    require(sha(raw) in APPROVED_SCRIPT, "Unapproved assertion producer snapshot")
    tree = ast.parse(raw.decode("utf-8"))
    functions = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name in PURE_NAMES]
    require({node.name for node in functions} == PURE_NAMES, "Pure function snapshot incomplete")
    module = ast.fix_missing_locations(ast.Module(body=functions, type_ignores=[]))
    namespace = {"shared": SimpleNamespace(strict=strict, canonical=canonical, sha=sha), "PROTOCOL": PROTOCOL}
    exec(compile(module, "<verified-assertion-pure-snapshot>", "exec"), namespace)
    return SimpleNamespace(**{name: namespace[name] for name in PURE_NAMES})


def exact_span(source, anchor):
    require(type(anchor) is dict and set(anchor) == {"quote", "occurrence"}, "Anchor fields")
    quote, occurrence = anchor["quote"], anchor["occurrence"]
    require(type(quote) is str and bool(quote), "Empty or nontext quote")
    require(type(occurrence) is int and occurrence > 0, "Anchor occurrence must be integer >0")
    offsets = [index for index in range(len(source)) if source.startswith(quote, index)]
    require(occurrence <= len(offsets), "Exact source quote occurrence absent")
    start = offsets[occurrence - 1]
    return {"quote": quote, "occurrence": occurrence, "start": start, "end_exclusive": start + len(quote)}


def independent_bindings(ir, source):
    """Independent type/reference/profile checks; no claim entailment inference."""
    require(set(ir) == {"entities", "assertions", "unresolved"}, "Top IR fields")
    require(all(type(ir[key]) is list for key in ir), "Top IR list types")
    ids = [item["id"] for item in ir["entities"] + ir["assertions"]]
    require(all(type(item) is str and item.strip() for item in ids) and len(set(ids)) == len(ids), "Global ID identity")
    entities = {item["id"]: item for item in ir["entities"]}
    assertions = {item["id"]: item for item in ir["assertions"]}
    bindings = []

    def anchor(item, path):
        bindings.append({"path": path, **exact_span(source, item)})

    for index, entity in enumerate(ir["entities"]):
        require(set(entity) == {"id", "mentions"} and bool(entity["mentions"]), "Entity fields/mentions")
        for position, mention in enumerate(entity["mentions"]):
            anchor(mention, f"/entities/{index}/mentions/{position}")
    profiles = []
    for index, item in enumerate(ir["assertions"]):
        require(item["kind"] in {"event", "state", "dependency"}, "Unknown assertion kind")
        require(all(type(item[k]) is str and item[k].strip() for k in ("claim", "predicate")), "Assertion text payload missing")
        require(bool(item["anchors"]), "Assertion evidence absent")
        for position, value in enumerate(item["anchors"]):
            anchor(value, f"/assertions/{index}/anchors/{position}")
        for position, arg in enumerate(item["arguments"]):
            require(set(arg) == {"ref", "role", "anchor"}, "Argument fields")
            require(type(arg["ref"]) is str and type(arg["role"]) is str and arg["role"].strip(), "Argument reference/role type")
            if item["kind"] == "dependency":
                require(arg["ref"] in assertions and assertions[arg["ref"]]["kind"] in {"event", "state"}, "Dependency known assertion reference/kind")
            else:
                require(arg["ref"] in entities, "Event/state known entity reference")
            anchor(arg["anchor"], f"/assertions/{index}/arguments/{position}/anchor")
        for position, value in enumerate(item["qualifiers"]):
            require(set(value) == {"claim", "anchors"} and type(value["claim"]) is str and value["claim"].strip() and bool(value["anchors"]), "Qualifier payload/evidence")
            for number, span in enumerate(value["anchors"]):
                anchor(span, f"/assertions/{index}/qualifiers/{position}/anchors/{number}")
        eligible = len(item["arguments"]) == 2 and not item["qualifiers"] and (item["kind"] != "dependency" or all(assertions[a["ref"]]["kind"] == "event" for a in item["arguments"]))
        binary = item["binary_projection"]
        if binary is None:
            require(not eligible or bool(ir["unresolved"]), "Eligible projection absent without unresolved")
        else:
            require(eligible and set(binary) == {"head", "relation", "tail"}, "Ineligible binary projection or fields")
            require(type(binary["relation"]) is str and binary["relation"].strip(), "Binary predicate absent")
            require([binary["head"], binary["tail"]] == [arg["ref"] for arg in item["arguments"]], "Projection role order mismatch")
        profiles.append({"assertion_id": item["id"], "kind": item["kind"], "argument_occurrences": len(item["arguments"]),
                         "distinct_references": len({arg["ref"] for arg in item["arguments"]}), "qualifier_count": len(item["qualifiers"]),
                         "binary_eligible": eligible, "binary_declared": binary is not None})
    require(all(type(value) is str and value.strip() for value in ir["unresolved"]), "Unresolved descriptions")
    return bindings, profiles


def inspect_graph(graph, ir, source, bindings):
    require(graph.is_directed() and graph.is_multigraph(), "Actual serialized graph is not MultiDiGraph")
    require(graph.graph["protocol"] == PROTOCOL and strict(graph.graph["unresolved_json"]) == ir["unresolved"], "Graph protocol/unresolved changed")
    require(set(graph.nodes) == {"source"} | {f"entity:{n}" for n in range(len(ir["entities"]))} | {f"assertion:{n}" for n in range(len(ir["assertions"]))}, "Physical node identity/count changed")
    require(graph.nodes["source"] == {"type": "source_text", "text": source, "source_sha256": sha(source.encode())}, "Physical source node changed")
    targets = {}
    for n, entity in enumerate(ir["entities"]):
        targets[entity["id"]] = f"entity:{n}"
        data = graph.nodes[f"entity:{n}"]
        require(data == {"type": "entity", "id": entity["id"], "position": n, "label": entity["mentions"][0]["quote"], "mentions_json": canonical(entity["mentions"]).decode()}, "Physical entity record changed")
    for n, assertion in enumerate(ir["assertions"]):
        targets[assertion["id"]] = f"assertion:{n}"
        data = graph.nodes[f"assertion:{n}"]
        expected = {"type": assertion["kind"], "id": assertion["id"], "position": n, "claim": assertion["claim"], "predicate": assertion["predicate"]}
        expected.update({key + "_json": canonical(assertion[key]).decode() for key in ("qualifiers", "anchors", "binary_projection")})
        require(data == expected, "Physical assertion payload/qualifier changed")
    expected_edges = {}
    for n, assertion in enumerate(ir["assertions"]):
        for position, arg in enumerate(assertion["arguments"]):
            expected_edges[(f"assertion:{n}", targets[arg["ref"]], f"argument:{n}:{position}")] = {
                "type": "argument", "position": position, "ref": arg["ref"], "role": arg["role"], "anchor_json": canonical(arg["anchor"]).decode()}
    for binding in bindings:
        fields = binding["path"].split("/")
        owner = f"{'entity' if fields[1] == 'entities' else 'assertion'}:{fields[2]}"
        expected_edges[(owner, "source", "evidence:" + binding["path"])] = {"type": "evidence", "field_path": binding["path"], **{k: v for k, v in binding.items() if k != "path"}}
    actual_edges = {(head, tail, key): dict(data) for head, tail, key, data in graph.edges(keys=True, data=True)}
    require(actual_edges == expected_edges, "Actual indexed role/evidence edges changed, lost or added")
    return {"physical_nodes": graph.number_of_nodes(), "physical_edges": graph.number_of_edges(),
            "argument_edges": sum(d["type"] == "argument" for d in actual_edges.values()), "evidence_edges": len(bindings)}


def source_inputs(folder, condition):
    matches = [TOOLS / name for name, digest in SOURCE_FILES.items() if digest == condition["fixture_file_sha256"]]
    require(len(matches) == 1 and sha(matches[0].read_bytes()) == condition["fixture_file_sha256"], "Fixture exact allowlist/source SHA")
    fixtures = read(matches[0])["fixtures"]
    if matches[0].name == "fixtures_assertion_ir_s0_regression_v3.json":
        prior = []
        for name, digest in SOURCE_FILES.items():
            if name == matches[0].name:
                continue
            path = TOOLS / name
            require(sha(path.read_bytes()) == digest, "Previous source fixture changed during merged-source verification")
            prior.extend({key: row[key] for key in ("id", "stage", "text")} for row in read(path)["fixtures"])
        for row in fixtures:
            source_only = {key: row[key] for key in ("id", "stage", "text")}
            require(prior.count(source_only) == 1, "Merged regression introduces unapproved source changes")
    selected = read(folder / "source_inputs.json")
    require(len(selected) == len(condition["sources"]), "Selected source count")
    for source, binding in zip(selected, condition["sources"]):
        require(set(source) == {"id", "stage", "text"} and type(source["stage"]) is int and type(source["text"]) is str, "Source-only fields/types")
        matching = [row for row in fixtures if row["id"] == source["id"]]
        require(len(matching) == 1 and {key: matching[0][key] for key in ("id", "stage", "text")} == source,
                "Selected source differs from frozen fixture or includes fixture metadata")
        require(binding == {"id": source["id"], "stage": source["stage"], "text_sha256": sha(source["text"].encode())}, "Condition source binding mismatch")
    require(len({row["id"] for row in selected}) == len(selected) and len({row["stage"] for row in selected}) == 1, "Source IDs/stage")
    return selected


def code_and_parameters(folder, condition):
    raw = (folder / "assertion_runner_source.py").read_bytes()
    require(sha(raw) == condition["script_sha256"] and sha(raw) in APPROVED_SCRIPT, "Producer source snapshot SHA")
    public_raw = (folder / "producer_contract.json").read_bytes()
    require(sha(public_raw) == condition["public_contract_sha256"] and sha(public_raw) in APPROVED_CONTRACT, "Public producer contract exact SHA")
    if "public_contract_path" in condition:
        public_path = Path(condition["public_contract_path"])
        require(public_path.parent.resolve() == TOOLS.resolve() and sha(public_path.read_bytes()) == sha(public_raw), "Selected public contract path/source bytes")
    bindings = {name.replace("\\", "/"): digest for name, digest in condition["runtime_code_bindings"].items()}
    require(bindings == RUNTIME_PINS, "Runtime code versions differ from approved transport/source helpers")
    for name, digest in bindings.items():
        snapshot = folder / ("shared_runner_source.py" if name.endswith("/runner.py") else "runtime_sources/" + name)
        require(sha(snapshot.read_bytes()) == digest, "Archived runtime helper source SHA differs: " + name)
    parameter_dir = RESULTS / "s0_treatment_original_extraction"
    intent_path = parameter_dir / "r1/calls/0000/native_intent.json"
    intent_raw = intent_path.read_bytes(); intent = strict(intent_raw)
    require(sha(intent_raw) == PARAMETER_INTENT_SHA, "Pinned native extraction parameter receipt changed")
    request_raw = intent_path.with_name("request.json").read_bytes()
    original_condition_raw = (parameter_dir / "condition.json").read_bytes(); original_condition = strict(original_condition_raw)
    descriptor = {"path": str(intent_path), "sha256": sha(intent_raw), "request_sha256": sha(request_raw),
                  "original_condition_sha256": sha(original_condition_raw), "original_runner_sha256": original_condition["runner_sha256"]}
    require(condition["native_kwargs_source"] == descriptor and condition["native_kwargs_recorded"] == intent["native_generation_kwargs"], "Native kwargs provenance changed")
    require(intent["phase"] == "entity_relation" and intent["wire_sha256"] == sha(request_raw) and intent["prompt_sha256"] == sha(canonical(intent["messages"])) and intent["native_generation_kwargs"]["max_new_tokens"] == 2048, "Native original intent binding")
    verified = condition["native_source_verification"]
    require(verified["commit"] == original_condition["original_commit"] and verified["files"] == original_condition["original_files"] and original_condition["arm"] == "original", "Pinned original source verification differs")
    original = ROOT / "Tools/ReferenceRepos/benchmark_autoschemakg_original"
    require(len(verified["files"]) == 69, "Original source inventory count")
    for name, binding in verified["files"].items():
        require(sha((original / name).read_bytes()) == binding["sha256"], "Original reference helper modified: " + name)
    return pure_source(raw), strict(public_raw)


def call_audit(folder, condition, messages):
    calls = sorted((folder / "calls").glob("[0-9][0-9][0-9][0-9]")) if (folder / "calls").exists() else []
    require(len(calls) <= 1 and (not calls or calls[0].name == "0000"), "Extra request or replay in one-call condition")
    if not calls:
        return {"physical_POSTs": 0, "unknown_executions": 0, "HTTP_client_seconds": 0.0, "provider_confirmed": False, "producer_text": None}
    call = calls[0]; intent = read(call / "native_intent.json"); request_raw = (call / "request.json").read_bytes()
    payload = {"payload": {"model": condition["model"], "messages": [{"role": row["role"], "content": {"text": row["content"]}} for row in messages]}}
    require(request_raw == canonical(payload), "Actual wire request not exact public contract plus source")
    require(intent["phase"] == "assertion_extraction" and intent["messages"] == messages and intent["original_native_messages"] == messages, "Native assertion intent/source-only messages changed")
    require(intent["native_generation_kwargs"] == condition["native_kwargs_recorded"] and intent["prompt_sha256"] == sha(canonical(messages)) and intent["wire_sha256"] == sha(request_raw), "Native intent kwargs/hash")
    for key in ("concept_source_context_added", "concept_edge_context_added", "concept_direction_contract_added"):
        require(intent[key] is False, "Unrequested concept intervention")
    for key in ("concept_edge_context_sha256", "concept_direction_contract_sha256", "sampling_and_caps_on_wire"):
        require(intent[key] is None, "Unrecorded effective configuration")
    receipt = read(call / "receipt.json")
    require(receipt["ordinal"] == 0 and receipt["phase"] == "assertion_extraction", "Receipt phase/ordinal")
    require(type(receipt["physical_dispatch_performed"]) is bool and type(receipt["unknown_execution"]) is bool, "Receipt bool counters")
    dispatched = receipt["physical_dispatch_performed"]
    if dispatched:
        require(read(call / "dispatch_started.json") == {"physical_POSTs": 1, "request_sha256": sha(request_raw)}, "Actual physical dispatch proof")
    require(receipt["actual_cost_USD"] is None and receipt["backend_output_token_cap"] is None and receipt["effective_sampling"] is None, "Fabricated monetary/cap/sampling estimate")
    text = None
    if receipt["raw_body_saved"]:
        raw = (call / "response.raw").read_bytes()
        require(receipt["response_bytes"] == len(raw) and receipt["response_sha256"] == sha(raw), "Raw provider response receipt SHA")
        if receipt["institutional_completion_confirmed"]:
            response = strict(raw); content = response.get("content")
            text = content.get("text") if type(content) is dict else content
            require(response.get("success") is True and type(text) is str and receipt["http_status"] == 200 and receipt["HTTP_body_complete"] is True and receipt["unknown_execution"] is False, "Confirmed response validity")
            metadata = receipt["response_metadata"]
            require(metadata["response_body_sha256"] == sha(raw) and metadata["response_body_bytes"] == len(raw) and metadata["credential_reflection"] is False, "Response metadata/hash")
    require(not receipt["institutional_completion_confirmed"] or text is not None, "Confirmed response unavailable")
    seconds = receipt["HTTP_client_seconds"]
    require(type(seconds) in {int, float} and seconds >= 0, "HTTP client seconds unavailable")
    return {"physical_POSTs": int(dispatched), "unknown_executions": int(receipt["unknown_execution"]),
            "HTTP_client_seconds": seconds, "provider_confirmed": receipt["institutional_completion_confirmed"], "producer_text": text}


def repetition_audit(folder, row, source, condition, pure, contract):
    require(read(folder / "repetition_summary.json") == row and row["semantic_PASS"] is False, "Repetition ledger or automatic semantic claim")
    call = call_audit(folder, condition, pure.messages(contract, source["text"]))
    require(row["physical_POSTs"] == call["physical_POSTs"] and row["unknown_executions"] == call["unknown_executions"], "Per-repetition physical counter differs")
    result = {"fixture_id": source["id"], "repetition": row["repetition"], **{key: value for key, value in call.items() if key != "producer_text"},
              "construction_completed": row["complete"], "source_semantics": "Requires separate frozen private source review; no automatic admission"}
    graph_names = ["assertion_graph.graphml", "recovered_IR.json", "graph_snapshot.json", "legacy_views.json", "coverage_manifest.json"]
    if call["producer_text"] is None:
        require(row["complete"] is False and not (folder / "producer_text.txt").exists() and not any((folder / name).exists() for name in graph_names), "Graph/output after unconfirmed execution")
        result["construction_status"] = "provider_unconfirmed_or_not_started"
        return result
    producer = (folder / "producer_text.txt").read_text(encoding="utf-8")
    require(producer == call["producer_text"], "Archived producer response changed")
    status = read(folder / "decoder_status.json")
    try:
        ir, bindings = pure.decode_ir(producer, source["text"])
    except Exception as error:
        require(status == {"protocol_valid": False, "error_class": type(error).__name__, "reason": str(error), "additional_POSTs": 0}, "Decoder rejection not reproduced exactly")
        require(row["complete"] is False and not (folder / "parsed_IR.json").exists() and not any((folder / name).exists() for name in graph_names), "Artifacts fabricated after decoder rejection")
        result.update(construction_status="decoder_rejected", protocol_valid=False)
        return result
    require(status == {"protocol_valid": True, "exact_source_spans_bound": True, "semantic_support_verified": False}, "Decoder success metadata")
    independent, profiles = independent_bindings(ir, source["text"])
    require(independent == bindings == read(folder / "anchor_bindings.json") and ir == read(folder / "parsed_IR.json"), "Parsed IR/source anchor bindings changed")
    result.update(protocol_valid=True, assertion_profiles=profiles)
    argument_refs = {argument["ref"] for assertion in ir["assertions"] for argument in assertion["arguments"]}
    unused_entities = [entity["id"] for entity in ir["entities"] if entity["id"] not in argument_refs]
    result["structural_source_coverage_diagnostics"] = {
        "entity_ids_unreferenced_by_assertion_arguments": unused_entities,
        "unreferenced_entity_count": len(unused_entities),
        "automatic_semantic_failure": False,
        "meaning": "An emitted entity without an assertion-argument reference is a structural review signal. It does not establish a missing source role or false world fact without independent source review. A zero-entity event alone is not this risk.",
    }
    if ir["unresolved"]:
        require(row["complete"] is False and not any((folder / name).exists() for name in graph_names), "Unresolved construction continued")
        result.update(construction_status="unresolved_halt", unresolved=ir["unresolved"])
        return result
    require(row["complete"] is True, "Valid resolved response missing full construction")
    import networkx as nx
    graph_path = folder / "assertion_graph.graphml"
    graph = nx.read_graphml(graph_path, force_multigraph=True)
    shape = inspect_graph(graph, ir, source["text"], bindings)
    recovered = pure.recover_graph(graph)
    require(recovered == ir == read(folder / "recovered_IR.json"), "Actual serialized graph does not recover ordered producer IR")
    signature = pure.graph_signature(graph)
    require(signature == read(folder / "graph_snapshot.json") == pure.graph_signature(pure.build_graph(ir, source["text"], bindings)), "Physical graph snapshot/rebuild mismatch")
    views, coverage = pure.legacy_views(ir)
    require(views == read(folder / "legacy_views.json") and coverage == read(folder / "coverage_manifest.json"), "Declared task projections/coverage changed")
    expected = {"IR_sha256": sha(canonical(ir)), "graphml_sha256": sha(graph_path.read_bytes()), "exact_ordered_round_trip": True,
                "entity_count": len(ir["entities"]), "assertion_count": len(ir["assertions"]), "node_kinds": dict(Counter(d["type"] for _, d in graph.nodes(data=True))),
                "argument_occurrences": sum(len(a["arguments"]) for a in ir["assertions"]), "legacy_counts": {key: len(value) for key, value in views.items()}}
    require(all(row.get(key) == value for key, value in expected.items()), "Saved complete count/hash ledger differs")
    result.update(construction_status="completed_technically", exact_actual_graph_recovery=True, **shape, **expected)
    return result


def audit_run(folder):
    condition_raw = (folder / "condition.json").read_bytes(); condition = strict(condition_raw)
    require(condition["protocol"] == PROTOCOL and condition["provider"] == "HAWKI", "Separate protocol/provider")
    require(condition["automatic_retries"] == 0 and condition["semantic_support_verified"] is False and condition["schema_quality_evaluated"] is False, "Retry/automatic quality claim")
    require(all(condition[key] is None for key in ("sampling_and_caps_on_wire", "effective_sampling", "provider_model_revision")), "Fabricated effective provider settings")
    require(type(condition["repetitions"]) is int and 1 <= condition["repetitions"] <= 10, "Repetition setting")
    selected = source_inputs(folder, condition)
    pure, contract = code_and_parameters(folder, condition)
    summary = read(folder / "summary.json")
    require(summary["protocol"] == PROTOCOL and summary["semantic_PASS"] is False and summary["schema_quality_evaluated"] is False, "Summary protocol/quality claim")
    planned = [(source["id"], n) for source in selected for n in range(1, condition["repetitions"] + 1)]
    actual = [(row["fixture_id"], row["repetition"]) for row in summary["runs"]]
    require(actual == planned[:len(actual)], "Attempted repetitions are not a no-replay planned prefix")
    require(len(actual) <= len(planned) and len(set(actual)) == len(actual), "Repeated/unplanned repetition")
    sources = {source["id"]: source for source in selected}
    rows = [repetition_audit(folder / row["fixture_id"] / f"r{row['repetition']}", row, sources[row["fixture_id"]], condition, pure, contract) for row in summary["runs"]]
    physical = sum(row["physical_POSTs"] for row in rows); unknown = sum(row["unknown_executions"] for row in rows)
    completed = sum(row["construction_completed"] for row in rows)
    require(summary["physical_POSTs"] == physical and summary["unknown_executions"] == unknown and summary["repetitions_completed"] == completed, "Run physical/completion ledger")
    expected_receipts = {folder / row["fixture_id"] / f"r{row['repetition']}" / "calls/0000/receipt.json" for row in summary["runs"] if (folder / row["fixture_id"] / f"r{row['repetition']}" / "calls/0000/receipt.json").exists()}
    require(set(folder.rglob("receipt.json")) == expected_receipts, "Unaccounted extra receipt/replay")
    if summary["complete"]:
        require(actual == planned and completed == len(planned) and summary["status"] == "completed_technically" and summary["failure_class"] is None, "Full completion counter/status")
    else:
        require(summary["status"] in {"failed", "unresolved"} and completed < len(planned) and summary["failure_class"] is not None, "Incomplete construction status")
        require(not rows or not rows[-1]["construction_completed"], "Failure after all attempted complete cells needs manual audit")
    return {"run": folder.relative_to(RESULTS).as_posix(), "condition_sha256": sha(condition_raw), "summary_sha256": sha((folder / "summary.json").read_bytes()),
            "public_contract_sha256": condition["public_contract_sha256"], "script_sha256": condition["script_sha256"], "model": condition["model"],
            "artifact_verification_passed": True, "construction_complete": summary["complete"], "construction_status": summary["status"],
            "planned_repetitions": len(planned), "attempted_repetitions": len(rows), "unexecuted_repetitions": len(planned) - len(rows),
            "completed_repetitions": completed, "physical_POSTs": physical, "unknown_executions": unknown,
            "HTTP_client_seconds": sum(row["HTTP_client_seconds"] for row in rows), "repetitions": rows,
            "semantic_gate": "Not inferred from technical completion; independent private source reviews required"}


def self_test():
    pure = pure_source((TOOLS / "assertion_runner.py").read_bytes())
    source = "Ada washed herself with water."
    anchor = lambda quote: {"quote": quote, "occurrence": 1}
    entity = {"id": "e1", "mentions": [anchor("Ada"), anchor("herself")]}
    assertion = {"id": "a1", "kind": "event", "claim": source, "predicate": "washed", "arguments": [], "qualifiers": [], "anchors": [anchor("washed")], "binary_projection": None}
    zero = {"entities": [], "assertions": [deepcopy(assertion)], "unresolved": []}
    unary = {"entities": [deepcopy(entity)], "assertions": [deepcopy(assertion)], "unresolved": []}
    unary["assertions"][0]["arguments"] = [{"ref": "e1", "role": "actor", "anchor": anchor("Ada")}]
    binary = deepcopy(unary); binary["assertions"][0]["arguments"].append({"ref": "e1", "role": "patient", "anchor": anchor("herself")})
    binary["assertions"][0]["binary_projection"] = {"head": "e1", "relation": "washed", "tail": "e1"}
    qualified = deepcopy(binary); qualified["assertions"][0]["qualifiers"] = [{"claim": "with water", "anchors": [anchor("with water")]}]; qualified["assertions"][0]["binary_projection"] = None
    nary = deepcopy(binary); nary["entities"].append({"id": "e2", "mentions": [anchor("water")]}); nary["assertions"][0]["arguments"].append({"ref": "e2", "role": "instrument", "anchor": anchor("water")}); nary["assertions"][0]["binary_projection"] = None
    state = deepcopy(binary); state["assertions"][0]["kind"] = "state"
    dependency = deepcopy(binary)
    dependency["assertions"].append({**deepcopy(assertion), "id": "a2"})
    dependency["assertions"].append({**deepcopy(assertion), "id": "d1", "kind": "dependency",
        "arguments": [{"ref": "a1", "role": "before", "anchor": anchor("washed")}, {"ref": "a2", "role": "after", "anchor": anchor("washed")}],
        "binary_projection": {"head": "a1", "relation": "precedes", "tail": "a2"}})
    state_dependency = deepcopy(dependency); state_dependency["assertions"][0]["kind"] = "state"; state_dependency["assertions"][2]["binary_projection"] = None
    outcomes = []
    import networkx as nx
    with tempfile.TemporaryDirectory() as temporary:
        for name, ir in [("zero_roles", zero), ("unary", unary), ("reflexive_two_role_one_identity", binary), ("qualified_binary_no_projection", qualified), ("nary_roles", nary),
                         ("state_no_manufactured_event", state), ("event_dependency", dependency), ("state_dependency_primary_only", state_dependency)]:
            decoded, bindings = pure.decode_ir(canonical(ir), source); independent, profiles = independent_bindings(decoded, source)
            require(bindings == independent, "Self-test independent span mismatch")
            path = Path(temporary) / (name + ".graphml"); nx.write_graphml(pure.build_graph(decoded, source, bindings), path)
            graph = nx.read_graphml(path, force_multigraph=True); shape = inspect_graph(graph, ir, source, bindings)
            require(pure.recover_graph(graph) == ir, "Self-test serialized graph role recovery")
            if name == "reflexive_two_role_one_identity":
                require(graph.number_of_edges("assertion:0", "entity:0") == 2, "Parallel reflexive role edges lost")
                tampered = graph.copy(); tampered.remove_edge("assertion:0", "entity:0", "argument:0:1")
                try:
                    inspect_graph(tampered, ir, source, bindings)
                except ValueError:
                    pass
                else:
                    raise ValueError("Audit failed to catch actual parallel role-edge deletion")
            if name == "qualified_binary_no_projection":
                tampered = graph.copy(); tampered.nodes["assertion:0"]["qualifiers_json"] = "[]"
                try:
                    inspect_graph(tampered, ir, source, bindings)
                except ValueError:
                    pass
                else:
                    raise ValueError("Audit failed to catch serialized qualifier deletion")
            views, _ = pure.legacy_views(ir)
            if name == "state_no_manufactured_event":
                require(views["event_entity_dict"] == [], "State manufactured into legacy event")
            if name == "state_dependency_primary_only":
                require(views["event_relation_dict"] == [], "State dependency manufactured into event relation")
            outcomes.append({"case": name, "passed": True, "profile": profiles, **shape})
    rejected = []
    unknown = deepcopy(unary); unknown["assertions"][0]["arguments"][0]["ref"] = "missing"
    wrongkind = deepcopy(unary); wrongkind["assertions"][0]["arguments"][0]["ref"] = "a1"
    missing_projection = deepcopy(binary); missing_projection["assertions"][0]["binary_projection"] = None
    invented_projection = deepcopy(unary); invented_projection["assertions"][0]["binary_projection"] = binary["assertions"][0]["binary_projection"]
    qualified_projection = deepcopy(qualified); qualified_projection["assertions"][0]["binary_projection"] = binary["assertions"][0]["binary_projection"]
    bad_anchor = deepcopy(unary); bad_anchor["entities"][0]["mentions"][0]["occurrence"] = True
    extra = deepcopy(unary); extra["gold"] = "never producer input"
    bad_dependency = deepcopy(state_dependency); bad_dependency["assertions"][2]["binary_projection"] = dependency["assertions"][2]["binary_projection"]
    duplicate_id = deepcopy(unary); duplicate_id["assertions"][0]["id"] = "e1"
    for name, ir in [("unknown_id", unknown), ("wrong_reference_kind", wrongkind), ("missing_eligible_projection", missing_projection), ("unary_binary_projection", invented_projection), ("qualified_binary_projection", qualified_projection), ("boolean_anchor_occurrence", bad_anchor), ("extra_field", extra),
                     ("state_dependency_binary_projection", bad_dependency), ("duplicate_global_identity", duplicate_id)]:
        try:
            pure.decode_ir(canonical(ir), source)
        except Exception:
            rejected.append({"case": name, "rejection_verified": True})
        else:
            raise ValueError("Self-test expected rejection: " + name)
    require(exact_span("aaaa", {"quote": "aa", "occurrence": 3}) == {"quote": "aa", "occurrence": 3, "start": 2, "end_exclusive": 4}, "Overlapping occurrence binding")
    unresolved = deepcopy(missing_projection); unresolved["unresolved"] = ["Representation requires review"]
    pure.decode_ir(canonical(unresolved), source)
    return {"protocol": "source-assertion-audit-offline-checks:oct14-v1", "model_calls": 0, "network_calls": 0,
            "synthetic_component_cases_only": True, "valid_graph_cases": outcomes, "rejection_cases": rejected,
            "overlapping_quotes_verified": True, "unresolved_formally_decodable_but_construction_halts": True,
            "tampered_parallel_role_edge_and_qualifier_deletions_rejected": True,
            "source_semantic_scores": None, "claim_limit": "Constructed transport counterchecks are not natural model outputs or source-semantic benchmark scores."}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--run", action="append", help="Owned run folder relative to results; omission audits all finalized new-protocol runs")
    parser.add_argument("--self-test", action="store_true", help="Synthetic CPU decoder/serialized-graph counterchecks only; no live cohort audit")
    args = parser.parse_args(argv)
    output = args.output.resolve()
    require(RESULTS.resolve() in output.parents and not output.exists(), "Output must be new in owned results")
    if args.self_test:
        require(not args.run, "Self-test does not inspect selected live runs")
        report = self_test()
    else:
        folders = [RESULTS / name for name in args.run] if args.run else sorted({path.parent for path in RESULTS.rglob("condition.json") if read(path).get("protocol") == PROTOCOL and (path.parent / "summary.json").exists() and read(path.parent / "summary.json").get("status") != "running"})
        require(len(set(path.resolve() for path in folders)) == len(folders), "Duplicate selected run folder")
        runs, failures = [], []
        for folder in folders:
            require(RESULTS.resolve() in folder.resolve().parents, "Run outside owned result tree")
            try:
                runs.append(audit_run(folder))
            except Exception as error:
                failures.append({"run": folder.relative_to(RESULTS).as_posix(), "error_class": type(error).__name__, "reason": str(error)})
        report = {"protocol": AUDIT_PROTOCOL, "new_fork_only": True, "legacy_native_totals_unchanged": True,
                  "audited_at_utc": datetime.now(timezone.utc).isoformat(), "auditor_source_sha256": sha(Path(__file__).read_bytes()),
                  "runs": runs, "failures": failures, "artifact_verification_passed": not failures,
                  "totals": {"run_folders": len(folders), "verified_run_folders": len(runs), "construction_completed_run_folders": sum(row["construction_complete"] for row in runs),
                             "construction_failed_or_unresolved_run_folders": sum(not row["construction_complete"] for row in runs),
                             "physical_POSTs": sum(row["physical_POSTs"] for row in runs), "unknown_executions": sum(row["unknown_executions"] for row in runs),
                             "completed_repetitions": sum(row["completed_repetitions"] for row in runs), "HTTP_client_seconds": sum(row["HTTP_client_seconds"] for row in runs)},
                  "analysis_model_calls": 0, "analysis_network_calls": 0, "semantic_gate": "Independent private source reviews required; technical completion is not source-quality admission",
                  "schema_quality_evaluated": False, "cost_limit": "Only saved physical POST counts and observed HTTP client durations. No tokens, price or dollar estimates. Legacy totals require a separately verified parent-owned ledger; this audit never combines them implicitly."}
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("xb") as stream:
        stream.write(canonical(report) + b"\n")
    print(json.dumps({"output": str(output), "sha256": sha(output.read_bytes()), "failures": len(report.get("failures", [])), "model_calls": 0}))
    return 1 if report.get("failures") else 0


if __name__ == "__main__":
    raise SystemExit(main())
