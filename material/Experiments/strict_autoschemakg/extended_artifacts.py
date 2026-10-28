"""Immutable input projections and lossless identities for the extended pilot."""
from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path
import re

from . import evaluation


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                     separators=(",", ":"), allow_nan=False).encode("utf-8")).hexdigest()


def native_node_projection(text):
    """Only for joining: json_to_csv.clean_text, never changing source items."""
    for original in ("\n", "\r", "\t", "\v", "\f", "\b", "\a", "\\e"):
        text = text.replace(original, " ")
    text = text.replace(";", ",").replace("\x00", "")
    return re.sub(r"\s+", " ", text).strip()


def source_passage(original_text):
    # InfoPreservation/question_generation.py passes data['original_text'] unchanged.
    return original_text


def inventory_extraction(path, construction_id):
    rows, _ = evaluation._extraction_rows(Path(path))
    result = []
    for row_index, row in enumerate(rows):
        extraction_id = f"{construction_id}:extraction:{row_index:04d}"
        source = row["original_text"]
        for category, field in (("entity", "entity_relation_dict"),
                                ("event", "event_entity_relation_dict"),
                                ("relation", "event_relation_dict")):
            for index, value in enumerate(row[field]):
                if not isinstance(value, dict):
                    raise ValueError(f"Invalid {field} item")
                result.append({"occurrence_id": f"{extraction_id}:{category}:{index:05d}",
                               "extraction_id": extraction_id, "category": category,
                               "item_index": index, "value": value, "content_sha256": digest(value),
                               "source": source, "source_sha256": hashlib.sha256(source.encode()).hexdigest()})
                if category == "event":
                    if not isinstance(value.get("Entity"), list):
                        raise ValueError("Native EV record requires Entity list")
                    for entity_index, entity in enumerate(value["Entity"]):
                        if not isinstance(entity, str):
                            raise ValueError("Native EV entity must be a string")
                        link = {"Event": value["Event"], "Entity": entity}
                        result.append({"occurrence_id": f"{extraction_id}:event_entity_link:{index:05d}:{entity_index:03d}",
                                       "extraction_id": extraction_id, "category": "event_entity_link",
                                       "item_index": index, "entity_index": entity_index, "value": link,
                                       "content_sha256": digest(link), "source": source,
                                       "source_sha256": hashlib.sha256(source.encode()).hexdigest()})
    return result


def native_context_record(extraction_path, questions):
    rows, _ = evaluation._extraction_rows(Path(extraction_path))
    if len(rows) != 1:
        raise ValueError("Extended pilot expects exactly one native extraction record")
    row = rows[0]
    return {"passage": source_passage(row["original_text"]),
            "entity_relation_list": [f"{x['Head']}, {x['Relation']}, {x['Tail']}" for x in row["entity_relation_dict"]],
            "event_entity_list": [f"{x['Event']}" for x in row["event_entity_relation_dict"]],
            "event_relation_list": [f"{x['Head']}, {x['Relation']}, {x['Tail']}" for x in row["event_relation_dict"]],
            "mcq_list": questions}


def load_questions(path):
    rows = evaluation._jsonl(Path(path))
    if len(rows) != 1 or len(rows[0].get("mcq_list", [])) != 5:
        raise ValueError("Fixed questions must be exactly one record with five MCQs")
    questions = rows[0]["mcq_list"]
    for question in questions:
        if (not isinstance(question, dict) or not isinstance(question.get("question"), str)
                or not isinstance(question.get("options"), list) or len(question["options"]) != 4
                or not all(isinstance(x, str) for x in question["options"])
                or not isinstance(question.get("answer"), str) or question["answer"] not in {"A", "B", "C", "D"}):
            raise ValueError("Each fixed MCQ requires question, four A-D options and a key")
    return questions


def inventory_concepts(path, construction_id, extractions):
    """Retain every CSV row and repeated comma-delimited concept occurrence."""
    by_category = {"entity": [], "event": [], "relation": []}
    for item in extractions:
        value = item["value"]
        if item["category"] == "entity":
            by_category["entity"].extend((native_node_projection(obj), item) for obj in (value["Head"], value["Tail"]))
            by_category["relation"].append((native_node_projection(value["Relation"]), item))
        elif item["category"] == "event":
            by_category["event"].append((native_node_projection(value["Event"]), item))
        elif item["category"] == "event_entity_link":
            by_category["entity"].append((native_node_projection(value["Entity"]), item))
        else:
            by_category["event"].extend((native_node_projection(obj), item) for obj in (value["Head"], value["Tail"]))
            by_category["relation"].append((native_node_projection(value["Relation"]), item))
    result = []
    with Path(path).open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        if reader.fieldnames != ["node", "conceptualized_node", "node_type"]:
            raise ValueError("Unexpected native concepts CSV header")
        for row_index, row in enumerate(reader):
            category = row["node_type"]
            if category not in by_category or not row["node"]:
                raise ValueError("Invalid native concept category or object")
            associated = [item for obj, item in by_category[category] if obj == row["node"]]
            for concept_index, concept in enumerate(row["conceptualized_node"].split(",")):
                # Preserve original spelling and duplicate entries; whitespace is not normalized.
                ident = f"{construction_id}:concept:{row_index:05d}:{concept_index:03d}"
                pair = {"object": row["node"], "concept": concept}
                result.append({"id": ident, "category": category, **pair,
                               "content_sha256": digest(pair), "csv_row": row_index,
                               "conceptualized_node_raw": row["conceptualized_node"],
                               "concept_index": concept_index,
                               "extraction_ids": list(dict.fromkeys(x["extraction_id"] for x in associated)),
                               "occurrence_ids": [x["occurrence_id"] for x in associated],
                               "source": associated[0]["source"] if associated else extractions[0]["source"],
                               "exact_object_linked": bool(associated),
                               "relevant_triples": [x["value"] for x in associated]})
    return result


def context(record, context_type):
    # Byte-for-byte native string construction from answer_generation.evaluate.
    if context_type == "passage":
        return record["passage"]
    if context_type == "entity":
        return "; ".join(record["entity_relation_list"])
    if context_type == "event_only":
        return "; ".join(record["event_entity_list"] + record["event_relation_list"])
    if context_type == "event":
        return "; ".join(record["event_entity_list"] + record["event_relation_list"]
                         + record["entity_relation_list"])
    if context_type == "empty":
        return "None"
    raise ValueError("Unknown native context")
