from __future__ import annotations

import argparse
import hashlib
import io
import json
import re
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path
from typing import Any

import networkx as nx

from triple_utils import _occurrence_records

BASE = Path(__file__).resolve().parent.parent
DATA = BASE / "data"
DEFAULT_EXTRACTION_ROOT = BASE / "results" / "extractions"
DEFAULT_OUTPUT_ROOT = BASE / "results" / "graphml"
GRAPHML_NS = "http://graphml.graphdrawing.org/xmlns"
YED_NS = "http://www.yworks.com/xml/graphml"

ET.register_namespace("", GRAPHML_NS)
ET.register_namespace("y", YED_NS)

_ILLEGAL_XML_RE = re.compile(
    "["
    + "\x00-\x08"
    + "\x0b"
    + "\x0c"
    + "\x0e-\x1f"
    + "\ud800-\udfff"
    + "\ufffe\uffff"
    + "]"
)


def _clean_text(value: Any) -> str:
    return re.sub(r"\s+", " ", str("" if value is None else value).strip())


def _safe_graphml_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (list, tuple, dict)):
        text = json.dumps(value, ensure_ascii=False)
    else:
        text = str(value)
    return _ILLEGAL_XML_RE.sub("", text)


def _graphml_tag(name: str) -> str:
    return f"{{{GRAPHML_NS}}}{name}"


def _yed_tag(name: str) -> str:
    return f"{{{YED_NS}}}{name}"


def _graphml_key_id(root: ET.Element, *, target: str, attr_name: str) -> str | None:
    for key in root.findall(_graphml_tag("key")):
        if key.get("for") == target and key.get("attr.name") == attr_name:
            return key.get("id")
    return None


def _graphml_data_text(element: ET.Element, key_id: str | None) -> str:
    if not key_id:
        return ""
    for data in element.findall(_graphml_tag("data")):
        if data.get("key") == key_id:
            return _clean_text(data.text)
    return ""


def _ensure_yed_key(
    root: ET.Element, *, key_id: str, target: str, yfiles_type: str
) -> None:
    if any(key.get("id") == key_id for key in root.findall(_graphml_tag("key"))):
        return
    key = ET.Element(
        _graphml_tag("key"),
        {
            "id": key_id,
            "for": target,
            "yfiles.type": yfiles_type,
        },
    )
    graph_index = next(
        (
            index
            for index, child in enumerate(list(root))
            if child.tag == _graphml_tag("graph")
        ),
        len(root),
    )
    root.insert(graph_index, key)


def _node_fill_color(node_type: str) -> str:
    return {
        "entity": "#FFF2CC",
        "event": "#DAE8FC",
        "concept": "#D5E8D4",
        "passage": "#E1D5E7",
    }.get(node_type, "#F5F5F5")


def _edge_line_color(edge_type: str) -> str:
    return {
        "Relation": "#4D4D4D",
        "Concept": "#6FAF6A",
        "Source": "#9673A6",
    }.get(edge_type, "#4D4D4D")


def _xml_preserving_carriage_returns(serialized: bytes) -> bytes:
    # XML 1.0 normalizes literal CR/CRLF during parsing. Character references
    # preserve the actual character, including after ElementTree reserializes
    # an lxml-written reference. Do not normalize the source text itself.
    return serialized.replace(b"\r", b"&#13;")


def write_graphml_preserving_text(graph: nx.MultiDiGraph, output_file: Path) -> None:
    """Write GraphML without XML line-ending normalization of text attributes."""
    serialized = io.BytesIO()
    nx.write_graphml(graph, serialized, infer_numeric_types=True)
    output_file.write_bytes(_xml_preserving_carriage_returns(serialized.getvalue()))


def _inject_yed_labels(output_file: Path) -> None:
    tree = ET.parse(output_file)
    root = tree.getroot()
    _ensure_yed_key(
        root, key_id="yed_node_graphics", target="node", yfiles_type="nodegraphics"
    )
    _ensure_yed_key(
        root, key_id="yed_edge_graphics", target="edge", yfiles_type="edgegraphics"
    )

    node_label_key = _graphml_key_id(root, target="node", attr_name="label")
    node_type_key = _graphml_key_id(root, target="node", attr_name="type")
    edge_relation_key = _graphml_key_id(root, target="edge", attr_name="relation")
    edge_type_key = _graphml_key_id(root, target="edge", attr_name="type")

    graph = root.find(_graphml_tag("graph"))
    if graph is None:
        raise ValueError(f"GraphML file has no graph element: {output_file}")

    for node in graph.findall(_graphml_tag("node")):
        label = _graphml_data_text(node, node_label_key) or node.get("id", "")
        node_type = _graphml_data_text(node, node_type_key)
        data = ET.SubElement(node, _graphml_tag("data"), {"key": "yed_node_graphics"})
        shape_node = ET.SubElement(data, _yed_tag("ShapeNode"))
        ET.SubElement(
            shape_node,
            _yed_tag("Fill"),
            {"color": _node_fill_color(node_type), "transparent": "false"},
        )
        ET.SubElement(
            shape_node,
            _yed_tag("BorderStyle"),
            {"color": "#4D4D4D", "type": "line", "width": "1.0"},
        )
        label_element = ET.SubElement(shape_node, _yed_tag("NodeLabel"))
        label_element.text = label
        ET.SubElement(shape_node, _yed_tag("Shape"), {"type": "roundrectangle"})

    for edge in graph.findall(_graphml_tag("edge")):
        relation = _graphml_data_text(edge, edge_relation_key)
        edge_type = _graphml_data_text(edge, edge_type_key)
        data = ET.SubElement(edge, _graphml_tag("data"), {"key": "yed_edge_graphics"})
        polyline = ET.SubElement(data, _yed_tag("PolyLineEdge"))
        ET.SubElement(
            polyline,
            _yed_tag("LineStyle"),
            {"color": _edge_line_color(edge_type), "type": "line", "width": "1.0"},
        )
        ET.SubElement(
            polyline, _yed_tag("Arrows"), {"source": "none", "target": "standard"}
        )
        if relation:
            label_element = ET.SubElement(polyline, _yed_tag("EdgeLabel"))
            label_element.text = relation

    serialized = io.BytesIO()
    tree.write(serialized, encoding="utf-8", xml_declaration=True)
    output_file.write_bytes(_xml_preserving_carriage_returns(serialized.getvalue()))


def _stable_node_id(node_type: str, label: str) -> str:
    digest = hashlib.sha256(f"{node_type}\0{label}".encode("utf-8")).hexdigest()[:24]
    return f"{node_type}:{digest}"


def _concepts(value: Any) -> list[str]:
    if not value:
        return []
    if isinstance(value, str):
        items = [value]
    elif isinstance(value, list):
        items = value
    else:
        return []
    concepts = []
    for item in items:
        if not isinstance(item, str):
            continue
        concept = _clean_text(item)
        if concept and concept not in concepts:
            concepts.append(concept)
    return concepts


def _merge_csv_attr(existing: str | None, value: str) -> str:
    values = [part for part in str(existing or "").split(",") if part]
    if value and value not in values:
        values.append(value)
    return ",".join(values)


def _endpoint_types(triple_type: str) -> tuple[str, str]:
    if triple_type == "EE":
        return "entity", "entity"
    if triple_type == "EV":
        return "event", "entity"
    if triple_type == "VV":
        return "event", "event"
    return "node", "node"


def add_graph_node(
    graph: nx.MultiDiGraph, label: str, node_type: str,
    *, identity_label: str | None = None, **attrs: Any,
) -> str:
    node_id = _stable_node_id(node_type, label if identity_label is None else identity_label)
    safe_attrs = {
        "id": _safe_graphml_value(label),
        "label": _safe_graphml_value(label),
        "type": _safe_graphml_value(node_type),
        **{
            key: _safe_graphml_value(value)
            for key, value in attrs.items()
            if value is not None
        },
    }
    if node_id not in graph:
        graph.add_node(node_id, **safe_attrs)
        return node_id

    node_attrs = graph.nodes[node_id]
    if safe_attrs.get("article_id"):
        node_attrs["article_id"] = _merge_csv_attr(
            node_attrs.get("article_id"), safe_attrs["article_id"]
        )
    if safe_attrs.get("chunk_id"):
        node_attrs["chunk_id"] = _merge_csv_attr(
            node_attrs.get("chunk_id"), safe_attrs["chunk_id"]
        )
    for key, value in safe_attrs.items():
        if key not in node_attrs or not node_attrs[key]:
            node_attrs[key] = value
    return node_id


def add_graph_edge_once(
    graph: nx.MultiDiGraph,
    source_id: str,
    target_id: str,
    edge_key: str,
    **attrs: Any,
) -> None:
    safe_attrs = {
        key: _safe_graphml_value(value)
        for key, value in attrs.items()
        if value is not None
    }
    if graph.has_edge(source_id, target_id, key=edge_key):
        graph.edges[source_id, target_id, edge_key].update(safe_attrs)
        return
    graph.add_edge(source_id, target_id, key=edge_key, **safe_attrs)


def load_corpus_index(data_dir: Path = DATA) -> dict[str, dict]:
    index: dict[str, dict] = {}
    for meta_file in (
        data_dir / "corpus_meta.json",
        data_dir / "corpus_extra_meta.json",
    ):
        if not meta_file.exists():
            continue
        records = json.loads(meta_file.read_text("utf-8"))
        for record in records:
            title = str(record.get("title", ""))
            if title:
                index[title] = record
    return index


def load_chunk_lookup(
    article_id: str, corpus_index: dict[str, dict], data_dir: Path = DATA
) -> dict[str, dict]:
    article_meta = corpus_index.get(article_id, {})
    file_stem = str(article_meta.get("file") or article_id)
    chunk_file = data_dir / "corpus" / f"{file_stem}_chunks.json"
    if not chunk_file.exists():
        return {}
    chunks = json.loads(chunk_file.read_text("utf-8"))
    return {str(chunk.get("chunk_id")): chunk for chunk in chunks}


def build_source_text_lookup(triples: list[dict], data_dir: Path = DATA) -> dict[str, str]:
    """Read original bytes once for explicitly bound character-slice origins.

    This deliberately does not consult legacy chunk files. Strict UTF-8 keeps
    BOM, CRLF and Unicode-codepoint offsets identical to the dispatch view.
    """
    corpus_index = load_corpus_index(data_dir)
    article_ids: set[str] = set()
    for triple in triples:
        for occurrence in _occurrence_records(triple):
            if "source_slice" not in occurrence:
                continue
            article_id = _clean_text(occurrence.get("article_id"))
            if not article_id:
                raise ValueError("Character-slice origin requires an article_id")
            article_ids.add(article_id)
    sources: dict[str, str] = {}
    for article_id in sorted(article_ids):
        file_stem = str(corpus_index.get(article_id, {}).get("file") or article_id)
        path = data_dir / "corpus" / f"{file_stem}.txt"
        sources[article_id] = path.read_bytes().decode("utf-8", errors="strict")
    return sources


def _source_slice_chunk(occurrence: dict, source: str | None, source_hash: str | None) -> dict:
    binding = occurrence.get("source_slice")
    if not isinstance(binding, dict):
        raise ValueError("Character-slice binding must be an object")
    start, end = binding.get("start_char"), binding.get("end_char")
    if (binding.get("chunking_protocol") != "source-slice-framing:v2"
            or binding.get("offset_unit") != "unicode_codepoints"
            or type(start) is not int or type(end) is not int
            or source is None or not 0 <= start < end <= len(source)
            or binding.get("source_text_sha256") != source_hash):
        raise ValueError("Missing, changed or invalid character-slice source binding")
    return {"text": source[start:end], "source_slice": binding,
            "start_char": start, "end_char": end,
            "offset_unit": binding["offset_unit"],
            "source_text_sha256": source_hash,
            "chunking_protocol": binding["chunking_protocol"]}


def _add_concept_edges(
    graph: nx.MultiDiGraph,
    source_id: str,
    concepts: list[str],
    article_id: str,
    chunk_id: str,
    concept_owner: str,
    source_slice: dict | None = None,
) -> None:
    for concept in concepts:
        concept_id = add_graph_node(
            graph, concept, "concept", article_id=article_id, chunk_id=chunk_id
        )
        # Preserve the paired origin for repeated assignments. Serializing the
        # pair avoids ambiguous delimiter joins and keeps the node identity.
        origin = [article_id, chunk_id]
        if source_slice is not None:
            origin.append(source_slice)
        origin_key = json.dumps(origin, sort_keys=True, separators=(",", ":"))
        edge_key = f"concept:{concept_owner}:{concept_id}:{origin_key}"
        add_graph_edge_once(
            graph,
            source_id,
            concept_id,
            edge_key,
            relation="has concept",
            type="Concept",
            article_id=article_id,
            chunk_id=chunk_id,
            source_slice=source_slice,
        )


def build_graph_from_triples(
    triples: list[dict],
    *,
    chunk_lookup_by_article: dict[str, dict[str, dict]] | None = None,
    source_text_by_article: dict[str, str] | None = None,
    include_text_nodes: bool = True,
    include_concepts: bool = True,
) -> tuple[nx.MultiDiGraph, dict]:
    graph = nx.MultiDiGraph()
    stats: Counter[str] = Counter()
    chunk_lookup_by_article = chunk_lookup_by_article or {}
    source_text_by_article = source_text_by_article or {}
    source_hashes = {
        article_id: hashlib.sha256(text.encode("utf-8", errors="strict")).hexdigest()
        for article_id, text in source_text_by_article.items()
    }

    for index, triple in enumerate(triples):
        if any(value is not None and not isinstance(value, str) for value in (
            triple.get("subject"), triple.get("predicate"), triple.get("object")
        )):
            stats["skipped_non_string_triples"] += 1
            continue
        subject = _clean_text(triple.get("subject"))
        predicate = _clean_text(triple.get("predicate"))
        object_value = _clean_text(triple.get("object"))
        if not subject or not predicate or not object_value:
            stats["skipped_incomplete_triples"] += 1
            continue

        article_id = _clean_text(triple.get("article_id")) or "unknown-article"
        chunk_id = _clean_text(triple.get("chunk_id")) or "unknown-chunk"
        triple_type = _clean_text(triple.get("triple_type")) or "unknown"
        subject_type, object_type = _endpoint_types(triple_type)

        subject_id = add_graph_node(
            graph, subject, subject_type, article_id=article_id, chunk_id=chunk_id
        )
        object_id = add_graph_node(
            graph, object_value, object_type, article_id=article_id, chunk_id=chunk_id
        )

        relation_concepts = _concepts(triple.get("predicate_concept_types"))
        occurrences = _occurrence_records(triple)
        add_graph_edge_once(
            graph,
            subject_id,
            object_id,
            f"triple:{index}",
            relation=predicate,
            type="Relation",
            triple_type=triple_type,
            article_id=article_id,
            chunk_id=chunk_id,
            predicate_id=_clean_text(triple.get("predicate_id")),
            concepts=relation_concepts,
            occurrence_records=occurrences if "_deduplication" in triple else None,
            source_slice=triple.get("source_slice"),
        )
        stats[f"triples_{triple_type}"] += 1

        # Keep one relation per supplied fact, but expose every stored origin.
        # Occurrence records are actual inputs/metadata revisions, not inferred
        # additional assertions or semantic support for an endpoint.
        for occurrence in occurrences:
            origin_article = _clean_text(occurrence.get("article_id")) or "unknown-article"
            origin_chunk = _clean_text(occurrence.get("chunk_id")) or "unknown-chunk"
            add_graph_node(graph, subject, subject_type, article_id=origin_article, chunk_id=origin_chunk)
            add_graph_node(graph, object_value, object_type, article_id=origin_article, chunk_id=origin_chunk)
            if include_text_nodes:
                origin_identity = [origin_article, origin_chunk]
                if "source_slice" in occurrence:
                    chunk = _source_slice_chunk(occurrence,
                        source_text_by_article.get(origin_article), source_hashes.get(origin_article))
                    # Different window contracts can reuse an integer chunk ID.
                    # Preserve their distinct bound passages instead of merging.
                    origin_identity.append(chunk["source_slice"])
                else:
                    chunk = chunk_lookup_by_article.get(origin_article, {}).get(origin_chunk, {})
                passage_label = f"{origin_article}#chunk-{origin_chunk}"
                # Identity belongs to the origin pair, not its display label.
                passage_id = add_graph_node(
                    graph,
                    passage_label,
                    "passage",
                    identity_label=json.dumps(origin_identity, sort_keys=True, separators=(",", ":")),
                    article_id=origin_article,
                    chunk_id=origin_chunk,
                    original_text=chunk.get("text", ""),
                    # XML cannot contain some otherwise valid UTF-8 characters.
                    # Retain the complete source through JSON escapes as well
                    # as the existing XML-safe display field.
                    original_text_json=json.dumps(chunk.get("text", ""), ensure_ascii=True),
                    start_word=chunk.get("start_word"),
                    end_word=chunk.get("end_word"),
                    source_slice=chunk.get("source_slice"),
                    start_char=chunk.get("start_char"),
                    end_char=chunk.get("end_char"),
                    offset_unit=chunk.get("offset_unit"),
                    source_text_sha256=chunk.get("source_text_sha256"),
                    chunking_protocol=chunk.get("chunking_protocol"),
                )
                for endpoint_id in (subject_id, object_id):
                    add_graph_edge_once(
                        graph,
                        endpoint_id,
                        passage_id,
                        f"source:{endpoint_id}:{passage_id}",
                        relation="mention in",
                        type="Source",
                        article_id=origin_article,
                        chunk_id=origin_chunk,
                        source_slice=chunk.get("source_slice"),
                    )

            if include_concepts:
                for endpoint_id, field, owner in (
                    (subject_id, "subject_concept_types", "subject"),
                    (object_id, "object_concept_types", "object"),
                ):
                    _add_concept_edges(
                        graph, endpoint_id, _concepts(occurrence.get(field)),
                        origin_article, origin_chunk, f"{owner}:{endpoint_id}",
                        source_slice=occurrence.get("source_slice"),
                    )

    stats["nodes"] = graph.number_of_nodes()
    stats["edges"] = graph.number_of_edges()
    stats["relation_edges"] = sum(
        1
        for _, _, _, data in graph.edges(keys=True, data=True)
        if data.get("type") == "Relation"
    )
    stats["source_edges"] = sum(
        1
        for _, _, _, data in graph.edges(keys=True, data=True)
        if data.get("type") == "Source"
    )
    stats["concept_edges"] = sum(
        1
        for _, _, _, data in graph.edges(keys=True, data=True)
        if data.get("type") == "Concept"
    )
    return graph, dict(stats)


def load_extraction_triples(
    input_dir: Path, article_titles: set[str] | None = None
) -> list[dict]:
    if not input_dir.exists():
        raise FileNotFoundError(f"Extraction directory not found: {input_dir}")
    triples: list[dict] = []
    for json_file in sorted(input_dir.glob("*.json")):
        if json_file.name.startswith("_"):
            continue
        article_title = json_file.stem
        if article_titles and article_title not in article_titles:
            continue
        data = json.loads(json_file.read_text("utf-8"))
        if not isinstance(data, list):
            raise ValueError(f"Extraction file must contain a JSON array: {json_file}")
        triples.extend(item for item in data if isinstance(item, dict))
    return triples


def build_chunk_lookups(
    triples: list[dict], data_dir: Path = DATA
) -> dict[str, dict[str, dict]]:
    corpus_index = load_corpus_index(data_dir)
    article_ids = sorted({
        _clean_text(occurrence.get("article_id"))
        for triple in triples for occurrence in _occurrence_records(triple)
        if occurrence.get("article_id") and "source_slice" not in occurrence
    })
    return {
        article_id: load_chunk_lookup(article_id, corpus_index, data_dir)
        for article_id in article_ids
    }


def write_graphml_with_stats(
    graph: nx.MultiDiGraph, stats: dict, output_file: Path
) -> Path:
    output_file.parent.mkdir(parents=True, exist_ok=True)
    write_graphml_preserving_text(graph, output_file)
    _inject_yed_labels(output_file)
    nx.read_graphml(output_file)
    stats_file = output_file.with_suffix(".stats.json")
    stats_file.write_text(json.dumps(stats, ensure_ascii=False, indent=2), "utf-8")
    return stats_file


def export_graphml(
    input_dir: Path,
    output_file: Path,
    *,
    data_dir: Path = DATA,
    article_titles: set[str] | None = None,
    include_text_nodes: bool = True,
    include_concepts: bool = True,
) -> tuple[Path, Path, dict]:
    triples = load_extraction_triples(input_dir, article_titles)
    chunk_lookups = build_chunk_lookups(triples, data_dir) if include_text_nodes else {}
    source_texts = build_source_text_lookup(triples, data_dir) if include_text_nodes else {}
    graph, stats = build_graph_from_triples(
        triples,
        chunk_lookup_by_article=chunk_lookups,
        source_text_by_article=source_texts,
        include_text_nodes=include_text_nodes,
        include_concepts=include_concepts,
    )
    stats.update(
        {
            "input_dir": str(input_dir),
            "output_file": str(output_file),
            "articles": len({
                _clean_text(occurrence.get("article_id"))
                for triple in triples for occurrence in _occurrence_records(triple)
            }),
            "triples_loaded": len(triples),
            "include_text_nodes": include_text_nodes,
            "include_concepts": include_concepts,
        }
    )
    stats_file = write_graphml_with_stats(graph, stats, output_file)
    return output_file, stats_file, stats


def _resolve_project_path(path: Path) -> Path:
    return path if path.is_absolute() else BASE / path


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Export AutoSchemaKG extraction JSONs to NetworkX GraphML"
    )
    parser.add_argument(
        "--model", help="Model id under results/extractions/<model>/<pipeline>"
    )
    parser.add_argument(
        "--pipeline", default="autoschemakg", help="Pipeline/config folder to export"
    )
    parser.add_argument(
        "--input-dir",
        type=Path,
        help="Direct extraction directory; overrides --model/--pipeline",
    )
    parser.add_argument("--extraction-root", type=Path, default=DEFAULT_EXTRACTION_ROOT)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument(
        "--output-file", type=Path, help="Explicit .graphml output path"
    )
    parser.add_argument("--output-name", default="kg.graphml")
    parser.add_argument(
        "--article-title",
        action="append",
        default=[],
        help="Restrict export to one article title; repeatable",
    )
    parser.add_argument(
        "--no-text-nodes",
        action="store_true",
        help="Skip passage nodes and Source edges",
    )
    parser.add_argument(
        "--no-concepts",
        action="store_true",
        help="Skip concept nodes and Concept edges",
    )
    args = parser.parse_args()

    if args.input_dir:
        input_dir = _resolve_project_path(args.input_dir)
        output_group = input_dir.name
    else:
        if not args.model:
            parser.error("--model is required unless --input-dir is provided")
        input_dir = (
            _resolve_project_path(args.extraction_root) / args.model / args.pipeline
        )
        output_group = args.model

    if args.output_file:
        output_file = _resolve_project_path(args.output_file)
    else:
        output_file = (
            _resolve_project_path(args.output_root)
            / output_group
            / args.pipeline
            / args.output_name
        )

    graphml_file, stats_file, stats = export_graphml(
        input_dir,
        output_file,
        article_titles=set(args.article_title) if args.article_title else None,
        include_text_nodes=not args.no_text_nodes,
        include_concepts=not args.no_concepts,
    )
    print(f"[graphml] wrote {graphml_file}")
    print(f"[graphml] wrote {stats_file}")
    print(
        f"[graphml] triples={stats['triples_loaded']} nodes={stats['nodes']} "
        f"edges={stats['edges']} relation_edges={stats['relation_edges']}"
    )


if __name__ == "__main__":
    main()

