"""CPU-only native-output retention contracts and an explicit AS_GRAPH view.

The original AutoSchemaKG DiGraph is never repaired or replaced here. Its
readback is a literal, occurrence-aware diagnostic, not source recall. The
separate lossless MultiDiGraph stores complete native objects and technical
field links. Equal labels index strings only; they do not establish identity.
No model, encoder, retriever or network client is created by this module.
"""
from __future__ import annotations

from collections import Counter
from copy import deepcopy
from hashlib import sha256
from io import BytesIO
import json
import math
from pathlib import Path

import networkx as nx


PROTOCOL = "fair-native-graph-contract:oct23-v1"
LOSSLESS_PROTOCOL = "explicit-AS_GRAPH-native-occurrences:oct23-v1"
EE, EV, SDK_EV, VV = (
    "entity_relation_dict", "event_entity_relation_dict", "event_entity_dict",
    "event_relation_dict",
)
NATIVE_CATEGORIES = {EE: "EE", EV: "EV", SDK_EV: "EV", VV: "VV"}


def _require(value, message):
    if not value:
        raise ValueError(message)


def _json(value):
    def check(item):
        if item is None or type(item) in (str, bool, int):
            return
        if type(item) is float and math.isfinite(item):
            return
        if type(item) is list:
            for child in item:
                check(child)
            return
        if type(item) is dict and all(type(key) is str for key in item):
            for child in item.values():
                check(child)
            return
        raise ValueError("Strict finite JSON with string keys required")
    check(value)
    return json.dumps(value, sort_keys=True, ensure_ascii=True,
                      separators=(",", ":"), allow_nan=False)


def digest(value):
    return sha256(_json(value).encode("ascii")).hexdigest()


def _text_sha(text):
    return sha256(text.encode("utf-8")).hexdigest()


def _name(value, what):
    _require(type(value) is str and bool(value), what + " must be nonempty")
    value.encode("utf-8")
    return value


def _strict_load(raw):
    def pairs(rows):
        result = {}
        for key, value in rows:
            _require(key not in result, "Duplicate JSON object key")
            result[key] = value
        return result
    def bad(value):
        raise ValueError("Nonfinite JSON constant: " + value)
    value = json.loads(raw, object_pairs_hook=pairs, parse_constant=bad)
    _json(value)
    return value


def source_registry(sources):
    """Validate exact text hashes and byte/codepoint spans without guessing.

    Sources are {id|source_id,text,sha256,spans?}; unrecognized metadata stays
    in the complete snapshot. Spans use {id,start,end_exclusive,sha256,
    coordinate_system}, with raw_file_bytes or unicode_codepoints. A missing
    spans list means the entire input, not a fabricated quotation/evidence.
    """
    _require(type(sources) is list and bool(sources), "Nonempty source list required")
    _json(sources)
    registry = {}
    for source in sources:
        _require(type(source) is dict, "Source object required")
        _require(not ("id" in source and "source_id" in source), "Ambiguous source ID aliases")
        ident = _name(source.get("id", source.get("source_id")), "source ID")
        text = source.get("text")
        _require(type(text) is str and source.get("sha256") == _text_sha(text), "Source text SHA mismatch")
        _require(ident not in registry, "Duplicate source ID")
        raw = text.encode("utf-8")
        declared = source.get("spans", [{"id": "full", "start": 0,
            "end_exclusive": len(raw), "sha256": source["sha256"],
            "coordinate_system": "raw_file_bytes"}])
        _require(type(declared) is list and bool(declared), "Source spans must be nonempty")
        spans = {}
        for span in declared:
            _require(type(span) is dict, "Span object required")
            sid = _name(span.get("id"), "span ID")
            start, end = span.get("start"), span.get("end_exclusive")
            coordinate = span.get("coordinate_system")
            _require(coordinate in {"raw_file_bytes", "unicode_codepoints"}, "Explicit span coordinates required")
            whole = raw if coordinate == "raw_file_bytes" else text
            _require(type(start) is int and type(end) is int and 0 <= start <= end <= len(whole),
                     "Invalid span bounds")
            selected = whole[start:end]
            try:
                selected = selected.decode("utf-8") if type(selected) is bytes else selected
            except UnicodeDecodeError:
                raise ValueError("Byte span splits a UTF-8 character") from None
            _require(sid not in spans and span.get("sha256") == _text_sha(selected),
                     "Duplicate span ID or span SHA mismatch")
            spans[sid] = {**deepcopy(span), "text": selected}
        registry[ident] = {"text": text, "sha256": source["sha256"], "spans": spans}
    return registry


def _native_fields(row):
    _require(type(row) is dict and EE in row and VV in row, "Complete native EE/EV/VV row required")
    _require((EV in row) != (SDK_EV in row), "Exactly one native EV field required")
    fields = (EE, EV if EV in row else SDK_EV, VV)
    for field in fields:
        _require(type(row[field]) is list, "Native categories must be lists")
        for value in row[field]:
            _require(type(value) is dict, "Whole native object required")
            if NATIVE_CATEGORIES[field] == "EV":
                _require(type(value.get("Event")) is str and type(value.get("Entity")) is list
                         and all(type(item) is str for item in value["Entity"]), "Native EV Event/Entity structure differs")
            else:
                _require(all(type(value.get(key)) is str for key in ("Head", "Relation", "Tail")),
                         "Native Head/Relation/Tail structure differs")
    return fields


def bind_native_inventory(native_rows, sources, *, row_bindings=None):
    """Preserve every object, EV group, extension and duplicate in input order.

    row_bindings is one {source_id,span_id} per native row. Without an explicit
    mapping, row.id must equal a real source ID and original_text the whole
    source. Context linkage is not per-statement evidence or semantic support.
    Empty native strings/lists are retained and diagnosed, never completed.
    """
    _require(type(native_rows) is list, "Ordered native rows required")
    _json(native_rows)
    registry = source_registry(sources)
    if row_bindings is None:
        row_bindings = [{"source_id": row.get("id"), "span_id": "full"} for row in native_rows]
    _require(type(row_bindings) is list and len(row_bindings) == len(native_rows),
             "Every native row needs an explicit source/span binding")
    records = []
    for row_index, (row, origin) in enumerate(zip(native_rows, row_bindings)):
        fields = _native_fields(row)
        _require(type(origin) is dict and set(origin) == {"source_id", "span_id"}, "Exact row source/span binding required")
        source_id, span_id = origin["source_id"], origin["span_id"]
        _require(source_id in registry and span_id in registry[source_id]["spans"], "Unknown source or span ID")
        source, span = registry[source_id], registry[source_id]["spans"][span_id]
        _require(type(row.get("original_text")) is str and row["original_text"] == span["text"],
                 "Native row text differs from bound source span")
        for field in fields:
            for record_index, value in enumerate(row[field]):
                identity = [source_id, source["sha256"], span_id, span["sha256"], row_index, field, record_index]
                ident = "statement:" + digest(identity)
                records.append({"record_id": ident, "unit_id": ident,
                    "source_id": source_id, "source_sha256": source["sha256"],
                    "span_id": span_id, "span_sha256": span["sha256"],
                    "row_index": row_index, "native_field": field,
                    "record_index": record_index, "category": NATIVE_CATEGORIES[field],
                    "value": deepcopy(value), "value_sha256": digest(value)})
    return {"protocol": PROTOCOL, "native_rows": deepcopy(native_rows),
        "sources": deepcopy(sources), "row_bindings": deepcopy(row_bindings), "records": records,
        "native_sha256": digest(native_rows), "source_manifest_sha256": digest(sources),
        "source_support_judged": False, "complete_source_recall_measured": False}


def _slots(record):
    value, category = record["value"], record["category"]
    if category == "EV":
        return [("/Event", "event", value["Event"])] + [
            ("/Entity/" + str(i), "entity", item) for i, item in enumerate(value["Entity"])]
    kind = "entity" if category == "EE" else "event"
    return [("/Head", kind, value["Head"]), ("/Tail", kind, value["Tail"])]


def _graph_snapshot(graph):
    # NetworkX adds empty GraphML default maps on reading; these contain no
    # original value. Nonempty defaults and all other additions remain errors.
    attrs = {key: value for key, value in graph.graph.items()
             if key not in {"node_default", "edge_default"} or value != {}}
    return {"graph": attrs, "nodes": dict(graph.nodes(data=True)),
            "edges": {(u, v, str(k)): dict(a) for u, v, k, a in graph.edges(keys=True, data=True)}}


def build_lossless_export(native_rows, sources, schema=None, *, row_bindings=None):
    """Separate AS_GRAPH method condition; never an original-SDK replacement.

    Whole native objects have their own statement node. Direct EE/VV edges and
    EV participation projections retain every parallel occurrence. Full EV
    objects (including empty participant lists and qualifications) remain on
    their statement node. Technical lexical label nodes do not solve identity.
    Schema is retained verbatim, never promoted to verified type/merge edges.
    This statement layer requires separate QA-consumer qualification.
    """
    bound = bind_native_inventory(native_rows, sources, row_bindings=row_bindings)
    _require(schema is None or type(schema) is dict, "Schema payload must be an object or None")
    _json(schema)
    payload = {key: deepcopy(bound[key]) for key in ("native_rows", "sources", "row_bindings")}
    payload["schema"] = deepcopy(schema)
    graph = nx.MultiDiGraph(protocol=LOSSLESS_PROTOCOL, method_condition="AS_GRAPH",
        snapshot_json=_json(payload), snapshot_sha256=digest(payload),
        identity_claim="technical source-local lexical index only; not referent identity",
        semantic_support_certified=False, source_recall_measured=False,
        original_hipporag2_consumer_qualified=False)
    registry = source_registry(sources)
    span_nodes = {}
    for source_id, source in registry.items():
        node = "source:" + digest(source_id)
        graph.add_node(node, type="source", source_id_json=_json(source_id),
                       text_json=_json(source["text"]), source_sha256=source["sha256"])
        for span_id, span in source["spans"].items():
            span_node = "span:" + digest([source_id, span_id])
            span_nodes[(source_id, span_id)] = span_node
            graph.add_node(span_node, type="source_span", source_id_json=_json(source_id),
                span_id_json=_json(span_id), span_json=_json(span), span_sha256=span["sha256"])
            graph.add_edge(span_node, node, key="span-of:" + span_node, type="SpanOf", relation="span_of")
    for record in bound["records"]:
        ident = record["record_id"]
        span_node = span_nodes[(record["source_id"], record["span_id"])]
        graph.add_node(ident, type="statement", category=record["category"],
            record_json=_json(record), native_json=_json(record["value"]),
            native_sha256=record["value_sha256"])
        graph.add_edge(ident, span_node, key="context:" + ident, type="Context", relation="from_context")
        endpoints = {}
        for path, kind, label in _slots(record):
            # Lexical index shared within a source, while statements and slot
            # edges remain distinct. This is not a claim about real identity.
            node = "label:" + digest([record["source_id"], kind, label])
            graph.add_node(node, type=kind, label_json=_json(label), source_id_json=_json(record["source_id"]))
            graph.add_edge(ident, node, key=ident + ":field:" + path, type="Field", relation="native_field", field_path=path)
            graph.add_edge(node, span_node, key=ident + ":source:" + path,
                type="Source", relation="from_context", record_id=ident, field_path=path)
            endpoints[path] = node
        if record["category"] == "EV":
            projections = [("/Event", "/Entity/" + str(i), "is participated by")
                           for i in range(len(record["value"]["Entity"]))]
        else:
            projections = [("/Head", "/Tail", record["value"]["Relation"])]
        for index, (head, tail, relation) in enumerate(projections):
            graph.add_edge(endpoints[head], endpoints[tail], key=ident + ":relation:" + str(index),
                type="Relation", relation_json=_json(relation), record_id=ident,
                category=record["category"], source_id_json=_json(record["source_id"]),
                span_id_json=_json(record["span_id"]), span_sha256=record["span_sha256"],
                projection_only=record["category"] == "EV")
    return graph


def recover_lossless_export(graph):
    """Recover only if every actual node, keyed edge and attribute is intact."""
    _require(graph.is_directed() and graph.is_multigraph()
             and graph.graph.get("protocol") == LOSSLESS_PROTOCOL, "Lossless native MultiDiGraph required")
    payload = _strict_load(graph.graph["snapshot_json"])
    _require(type(payload) is dict and set(payload) == {"native_rows", "sources", "row_bindings", "schema"}
             and digest(payload) == graph.graph.get("snapshot_sha256"), "Lossless snapshot binding differs")
    expected = build_lossless_export(payload["native_rows"], payload["sources"], payload["schema"],
                                    row_bindings=payload["row_bindings"])
    _require(_graph_snapshot(graph) == _graph_snapshot(expected),
             "Missing, invented or changed native occurrence, field, provenance or schema")
    return deepcopy(payload)


def export_lossless_graphml(graph, output):
    """Reuse the existing CR-preserving writer and verify serialized recovery."""
    expected = recover_lossless_export(graph)
    output = Path(output)
    _require(output.parent.is_dir() and not output.exists(), "Fresh GraphML path with existing parent required")
    # Existing writer, not a second XML-cleaning/replacement implementation.
    from Tools.experiments.autoschema_ladder_oct14_v1.graph_probe import write_graphml_preserving_text
    write_graphml_preserving_text(graph, output)
    loaded = nx.read_graphml(output, force_multigraph=True)
    _require(recover_lossless_export(loaded) == expected, "GraphML native payload roundtrip differs")
    return {"protocol": LOSSLESS_PROTOCOL, "method_condition": "AS_GRAPH",
        "path": str(output.resolve()), "sha256": sha256(output.read_bytes()).hexdigest(),
        "whole_native_objects": len(bind_native_inventory(expected["native_rows"], expected["sources"],
                                   row_bindings=expected["row_bindings"])["records"]),
        "roundtrip_equal": True, "source_recall_measured": False,
        "source_support_judged": False, "original_hipporag2_consumer_qualified": False}


def read_lossless_graphml(path, *, expected_sha256):
    raw = Path(path).read_bytes()
    _require(sha256(raw).hexdigest() == expected_sha256, "GraphML SHA mismatch")
    return recover_lossless_export(nx.read_graphml(BytesIO(raw), force_multigraph=True))


def build_parallel_sdk_export(original_graph, relation_rows):
    """Consumable AS_GRAPH derivative over actual SDK CSV relation rows.

    Original node IDs/types/attributes and all non-Relation edges are retained.
    Each actual CSV row gets one keyed edge. Original per-pair attributes are
    retained; only relation/type come from that row. The entire CSV row remains
    in csv_row_json. Original merged concept attributes remain merged, and no
    lost native field, EV grouping or missing source link is inferred/repaired.
    No label cleaning, hash-ID formula or real-world identity is guessed.
    """
    _require(original_graph.is_directed() and not original_graph.is_multigraph(),
             "Actual original SDK DiGraph required")
    _require(type(relation_rows) is list and all(type(row) is dict for row in relation_rows),
             "Complete actual CSV rows required")
    _json(relation_rows)
    index = {}
    for node, attrs in original_graph.nodes(data=True):
        _require(all(type(attrs.get(key)) is str and bool(attrs[key]) for key in ("id", "type", "file_id")),
                 "Original SDK node attributes incomplete")
        if attrs["type"] in {"entity", "event"}:
            index.setdefault(attrs["id"], []).append(node)
    # Same established multi-edge and CR-preserving writer helpers as the
    # earlier graph_component probe. Its narrow FIELDS would discard real CSV
    # concepts/synsets, so it cannot itself be used as a full CSV-row adapter.
    from Tools.experiments.autoschema_ladder_oct14_v1.graph_probe import add_graph_edge_once
    graph = nx.MultiDiGraph(**deepcopy(original_graph.graph))
    graph.graph.update(export_condition="AS_GRAPH_parallel_original_csv_v1",
        csv_rows_json=_json(relation_rows), csv_rows_sha256=digest(relation_rows),
        complete_native_object_retention=False, source_provenance_repaired=False,
        original_label_identity_policy_retained=True)
    graph.add_nodes_from((node, deepcopy(attrs)) for node, attrs in original_graph.nodes(data=True))
    seen_pairs = set()
    for ordinal, row in enumerate(relation_rows):
        required = (":START_ID", ":END_ID", "relation", ":TYPE")
        _require(all(type(row.get(key)) is str for key in required)
                 and row[":TYPE"] == "Relation" and bool(row["relation"]), "SDK relation CSV row incomplete")
        ends = []
        for key in (":START_ID", ":END_ID"):
            matches = index.get(row[key], [])
            _require(len(matches) == 1, "Missing or ambiguous original SDK endpoint: " + row[key])
            ends.append(matches[0])
        head, tail = ends
        _require(original_graph.has_edge(head, tail)
                 and original_graph.edges[head, tail].get("type") == "Relation",
                 "CSV row has no original SDK relation-pair witness")
        attrs = deepcopy(original_graph.edges[head, tail])
        attrs.update(relation=row["relation"], type=row[":TYPE"],
            csv_row_json=_json(row), csv_row_ordinal=ordinal)
        add_graph_edge_once(graph, head, tail, "csv-row:" + str(ordinal).zfill(12), **attrs)
        seen_pairs.add((head, tail))
    original_pairs = {(head, tail) for head, tail, attrs in original_graph.edges(data=True)
                      if attrs.get("type") == "Relation"}
    _require(seen_pairs == original_pairs, "CSV rows do not cover every original SDK relation pair")
    for ordinal, (head, tail, attrs) in enumerate(original_graph.edges(data=True)):
        if attrs.get("type") != "Relation":
            add_graph_edge_once(graph, head, tail, "original-auxiliary:" + str(ordinal), **deepcopy(attrs))
    return graph


def verify_parallel_sdk_export(original_graph, relation_rows, graph):
    expected = build_parallel_sdk_export(original_graph, relation_rows)
    _require(_graph_snapshot(expected) == _graph_snapshot(graph),
             "Parallel SDK derivative lost/changed CSV rows, original nodes or auxiliary edges")
    return {"method_condition": "AS_GRAPH_parallel_original_csv_v1",
        "original_relation_edges": sum(attrs.get("type") == "Relation" for _, _, attrs in original_graph.edges(data=True)),
        "actual_csv_relation_rows": len(relation_rows),
        "retained_csv_relation_occurrences": sum(attrs.get("type") == "Relation" for _, _, attrs in graph.edges(data=True)),
        "complete_native_EV_object_retention": False, "source_provenance_repaired": False,
        "source_support_judged": False, "source_recall_measured": False,
        "original_nodes_and_auxiliary_edges_unchanged": True,
        "boundary": "Actual CSV-row retention only; prior native-to-CSV losses, identity merges and merged concepts remain."}


def export_parallel_sdk_graphml(original_graph, relation_rows, output):
    graph = build_parallel_sdk_export(original_graph, relation_rows)
    output = Path(output)
    _require(output.parent.is_dir() and not output.exists(), "Fresh parallel GraphML output required")
    from Tools.experiments.autoschema_ladder_oct14_v1.graph_probe import write_graphml_preserving_text
    write_graphml_preserving_text(graph, output)
    reread = nx.read_graphml(output, force_multigraph=True)
    proof = verify_parallel_sdk_export(original_graph, relation_rows, reread)
    return {**proof, "path": str(output.resolve()), "sha256": sha256(output.read_bytes()).hexdigest(),
            "graphml_roundtrip_equal": True, "QA_quality_measured": False}


def audit_sdk_export(native_rows, sources, graph, *, row_bindings=None, label_transform=None):
    """Read-only literal inventory→SDK graph comparison, with multiplicities.

    The optional caller-supplied original cleaning function is applied only to
    this diagnostic's comparison keys, never to the inventory or graph. Its
    origin must be separately pinned by the caller. A literal absent projection
    does not establish lost source meaning. Text nodes alone count no relation.
    """
    bound = bind_native_inventory(native_rows, sources, row_bindings=row_bindings)
    _require(graph.is_directed(), "Directed SDK graph required")
    transform = label_transform or (lambda value: value)
    expected, provenance, empty = [], set(), []
    for record in bound["records"]:
        value = record["value"]
        if record["category"] == "EV":
            projected = [(value["Event"], "is participated by", item) for item in value["Entity"]]
        else:
            projected = [(value["Head"], value["Relation"], value["Tail"])]
        for index, triple in enumerate(projected):
            cleaned = tuple(transform(item) for item in triple)
            _require(all(type(item) is str for item in cleaned), "Label transform must return strings")
            expected.append({"record_id": record["record_id"], "category": record["category"],
                "projection_index": index, "triple": list(cleaned), "native_triple": list(triple)})
            if any(not item for item in cleaned):
                empty.append({"record_id": record["record_id"], "projection_index": index})
            for endpoint in (cleaned[0], cleaned[2]):
                provenance.add((endpoint, native_rows[record["row_index"]]["original_text"]))
    expected_counts = Counter(tuple(row["triple"]) for row in expected)
    actual, actual_sources, missing_attributes = Counter(), set(), []
    label = lambda node: graph.nodes[node].get("id", graph.nodes[node].get("label"))
    for node, attrs in graph.nodes(data=True):
        if not all(type(attrs.get(key)) is str and bool(attrs[key]) for key in ("id", "type", "file_id")):
            missing_attributes.append(str(node))
    for head, tail, attrs in graph.edges(data=True):
        if attrs.get("type") == "Relation":
            values = (label(head), attrs.get("relation"), label(tail))
            if all(type(value) is str for value in values):
                actual[values] += 1
        if attrs.get("type") == "Source" and graph.nodes[tail].get("type") == "passage":
            actual_sources.add((label(head), label(tail)))
    missing, extra = expected_counts - actual, actual - expected_counts
    available = actual.copy()
    rows = []
    for row in expected:
        triple = tuple(row["triple"])
        retained = available[triple] > 0
        if retained:
            available[triple] -= 1
        rows.append({**row, "literal_occurrence_represented": retained})
    count = lambda counter: sum(counter.values())
    return {"protocol": PROTOCOL, "original_graph_modified": False,
        "native_objects": len(bound["records"]),
        "native_EV_objects": sum(row["category"] == "EV" for row in bound["records"]),
        "native_projected_slots": len(expected), "native_unique_projected_triples": len(expected_counts),
        "graph_relation_occurrences": count(actual), "graph_unique_relation_triples": len(actual),
        "retained_literal_occurrences": len(expected) - count(missing),
        "unrepresented_literal_occurrences": count(missing),
        "unrepresented_distinct_literal_triples": len(set(expected_counts) - set(actual)),
        "distinct_triples_with_occurrence_deficit": len(missing),
        "extra_graph_relation_occurrences": count(extra),
        "empty_native_projection_slots": empty,
        "missing_native_node_attribute_ids": missing_attributes,
        "expected_distinct_endpoint_context_pairs": len(provenance),
        "unrepresented_endpoint_context_pairs": len(provenance - actual_sources),
        "projection_rows": rows,
        "missing_projection_multiplicities": [{"triple": list(triple), "count": n} for triple, n in sorted(missing.items())],
        "literal_label_transform_applied": label_transform is not None,
        "source_echo_counts_as_statement_coverage": False,
        "per_statement_source_support_verified": False, "source_recall_measured": False,
        "semantic_equivalence_judged": False,
        "boundary": "Output retention only; endpoint context links are not per-fact entailment or referent identity."}


def bind_artifacts(native_rows, sources, schema, *, system, graph_path, graph_sha256, row_bindings=None):
    """Common AS/MM artifact shape, while retaining the actual export condition."""
    _name(system, "system")
    _require(type(schema) is dict, "Complete supplied schema object required")
    _json(schema)
    bound = bind_native_inventory(native_rows, sources, row_bindings=row_bindings)
    raw = Path(graph_path).read_bytes()
    _require(sha256(raw).hexdigest() == graph_sha256, "Actual graph SHA mismatch")
    graph = nx.read_graphml(BytesIO(raw), force_multigraph=True)
    graph_protocol = graph.graph.get("protocol")
    declared_condition = graph.graph.get("export_condition")
    if graph_protocol == LOSSLESS_PROTOCOL:
        _require(declared_condition is None, "Conflicting lossless graph export condition")
        export_condition = "AS_GRAPH"
        restored = recover_lossless_export(graph)
        _require(restored == {"native_rows": native_rows, "sources": sources,
            "row_bindings": bound["row_bindings"], "schema": schema}, "Graph differs from bound inventory/source/schema")
        report = {"lossless_native_roundtrip": True, "original_hipporag2_consumer_qualified": False}
    else:
        _require(graph_protocol is None and declared_condition in (
            None, "original_native_graph", "AS_GRAPH_parallel_original_csv_v1"),
            "Unknown graph protocol or export condition")
        export_condition = declared_condition or "original_native_graph"
        report = audit_sdk_export(native_rows, sources, graph, row_bindings=bound["row_bindings"])
    return {**bound, "system": system, "schema": deepcopy(schema), "schema_sha256": digest(schema),
        "graph": {"path": str(Path(graph_path).resolve()), "sha256": graph_sha256,
                  "export_condition": export_condition, "graph_protocol": graph_protocol,
                  "original_native_export": export_condition == "original_native_graph"},
        "graph_readback": report, "semantic_quality_certified": False,
        "schema_validation": "Complete supplied payload bound unchanged; schema truth and completeness not certified."}
