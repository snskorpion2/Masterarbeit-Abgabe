"""Narrow final-Relation-CSV control, following graph_probe.preserve_relation_rows.

This qualification covers the original include_concept=True final export.
The caller supplies the original final graph produced from the same frozen CSV
pack and an explicit original endpoint-ID binding. Nodes and original auxiliary
edges are copied, not reconstructed. Earlier node/source/auxiliary collapses are
not repaired. This is not a replacement six-CSV exporter, KGC method or QA run.

Each Relation CSV record gets its own position key. All original field strings
are retained in native_csv_row_json, including empty values and extra columns.
Operative concepts use the original release encoding for that record only.
Synsets are additional native_csv_synsets, not an original final-graph field.
Existing helpers retain their GraphML sanitation; raw values remain in JSON.
"""
from __future__ import annotations

from collections import Counter
import ast
import csv
from hashlib import sha256
import io
import json
from pathlib import Path
import sys

import networkx as nx

# Reuse the established generic edge/writer helpers without changing them.
_src = str(Path(__file__).resolve().parents[3] / "Experiments/src")
_path = list(sys.path)
try:
    sys.path.insert(0, _src)
    from graphml_export import add_graph_edge_once, write_graphml_preserving_text, _safe_graphml_value
finally:
    sys.path[:] = _path

PROTOCOL = "as-final-relation-row-export-control:oct20-v2"
REQUIRED = {":START_ID", ":END_ID", "relation", ":TYPE"}


def read_rows(path):
    raw = Path(path).read_bytes()
    reader = csv.DictReader(io.StringIO(raw.decode("utf-8-sig"), newline=""))
    fields = reader.fieldnames
    if not fields or len(set(fields)) != len(fields) or not REQUIRED <= set(fields):
        raise ValueError("Unique native Relation CSV headers required")
    rows = list(reader)
    if any(set(row) != set(fields) or any(type(v) is not str for v in row.values())
           or row[":TYPE"] != "Relation" for row in rows):
        raise ValueError("Only complete native Relation CSV records are supported")
    return raw, fields, rows


def auxiliary_multiset(graph):
    return Counter((u, v, json.dumps(attrs, sort_keys=True, ensure_ascii=True))
        for u, v, attrs in graph.edges(data=True) if attrs.get("type") != "Relation")


def original_row_concepts(value):
    """Exact release200-212 encoding with an initially empty single-row edge.

This is technical attribute serialization, not concept inference. The untouched
CSV field remains in row JSON, including duplicates hidden by release encoding.
"""
    current = None
    try:
        for concept in ast.literal_eval(value):
            text = _safe_graphml_value("" if concept is None else str(concept))
            if current is None:
                current = text
            elif text not in current.split(","):
                current += "," + text
    except (ValueError, SyntaxError):
        pass
    return current


def export_control(original_graph, relation_csv, endpoint_ids, output_file):
    """Write a fresh derivative; endpoint_ids is explicit, not inferred from labels."""
    if not original_graph.is_directed():
        raise ValueError("Original directed final graph required")
    output = Path(output_file)
    if output.exists():
        raise ValueError("Fresh control output required")
    raw, fields, rows = read_rows(relation_csv)
    graph = nx.MultiDiGraph()
    graph.graph.update(original_graph.graph)
    graph.add_nodes_from((key, dict(attrs)) for key, attrs in original_graph.nodes(data=True))
    for ordinal, row in enumerate(rows, 1):
        try:
            start, end = (endpoint_ids[row[name]] for name in (":START_ID", ":END_ID"))
        except KeyError:
            raise ValueError("Missing explicit original endpoint binding") from None
        if start not in graph or end not in graph:
            raise ValueError("Bound endpoint is absent from the original final graph")
        if (graph.nodes[start].get("id") != row[":START_ID"]
                or graph.nodes[end].get("id") != row[":END_ID"]):
            raise ValueError("Endpoint label binding differs; original label aliases are outside this control")
        attrs = {"relation": row["relation"], "type": row[":TYPE"],
                 "native_csv_record": str(ordinal),
                 "native_csv_row_json": json.dumps(row, ensure_ascii=True)}
        if "concepts" in row:
            encoded = original_row_concepts(row["concepts"])
            if encoded is not None:
                attrs["concepts"] = encoded
        if "synsets" in row and row["synsets"] != "":
            attrs["native_csv_synsets"] = row["synsets"]
        add_graph_edge_once(graph, start, end, f"native-triple-csv:{ordinal}", **attrs)
    for ordinal, (start, end, attrs) in enumerate(original_graph.edges(data=True)):
        if attrs.get("type") != "Relation":
            add_graph_edge_once(graph, start, end, f"original-auxiliary:{ordinal}", **attrs)
    graph.graph.update(export_control_protocol=PROTOCOL,
        native_relation_csv_sha256=sha256(raw).hexdigest(),
        native_relation_csv_columns=json.dumps(fields, ensure_ascii=True))
    if Path(relation_csv).read_bytes() != raw:
        raise ValueError("Frozen Relation CSV changed during construction")
    write_graphml_preserving_text(graph, output)
    reloaded = nx.read_graphml(output, force_multigraph=True)
    recovered = {}
    for start, end, key, attrs in reloaded.edges(keys=True, data=True):
        if attrs.get("type") == "Relation":
            ordinal = int(attrs["native_csv_record"])
            if (attrs["native_csv_record"] != str(ordinal) or ordinal < 1
                    or ordinal in recovered or key != f"native-triple-csv:{ordinal}"):
                raise ValueError("Control occurrence binding changed on readback")
            row = json.loads(attrs["native_csv_row_json"])
            if (endpoint_ids[row[":START_ID"]], endpoint_ids[row[":END_ID"]]) != (start, end):
                raise ValueError("Control endpoint binding changed on readback")
            if attrs.get("relation") != row["relation"]:
                raise ValueError("Control Relation field changed on readback")
            if (attrs.get("concepts") != (original_row_concepts(row["concepts"]) if "concepts" in row else None)
                    or attrs.get("native_csv_synsets") != (row.get("synsets") or None)):
                raise ValueError("Control per-record concept encoding or native synset field changed")
            recovered[ordinal] = row
    if ([recovered[k] for k in sorted(recovered)] != rows
            or dict(reloaded.nodes(data=True)) != dict(original_graph.nodes(data=True))
            or auxiliary_multiset(reloaded) != auxiliary_multiset(original_graph)
            or Path(relation_csv).read_bytes() != raw):
        raise ValueError("Control changed native rows, original nodes or auxiliary edges")
    return {"protocol": PROTOCOL, "native_relation_csv_sha256": sha256(raw).hexdigest(),
        "native_relation_csv_bytes": len(raw), "relation_records": len(rows),
        "explicit_original_endpoint_ids": dict(endpoint_ids),
        "node_attributes_unchanged": True, "auxiliary_edges_unchanged": True,
        "all_original_row_fields_recovered_exactly": True,
        "operative_concepts": "Original release encoding, independently for each CSV record; no pair union",
        "native_csv_synsets": "Additional original CSV information; original final exporter ignores synsets",
        "graphml_sha256": sha256(output.read_bytes()).hexdigest(),
        "scope": "Final Relation CSV rows only; original auxiliary scaffold retained",
        "source_truth_or_QA_measured": False, "new_model_calls": 0}
