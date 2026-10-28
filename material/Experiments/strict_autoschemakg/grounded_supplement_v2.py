"""Bounded GraphRAG-inspired continuation and Graphusion-inspired completion.

Source checks, directed native graphs and unrestricted relation names are local
adaptations. The original implementations/results are not overwritten.
"""
from __future__ import annotations

from copy import deepcopy
import json

from . import grounded_evidence_v1 as e, reliability_v2 as r
from . import completion_contracts as c, supplement_diagnostics_v1 as old


def glean_request(category, history, evidence, round_number, max_rounds=3):
    if not 1 <= round_number <= max_rounds:
        raise ValueError("Gleaning round outside declared budget")
    schema = r.obj({"candidates": r.array(e.candidate_schema(category, evidence))})
    prompt = (
        "Continue the preceding extraction. Search for omitted facts of category " + category + ". "
        "Find both missing entities/events and missing relations between already present endpoints. "
        "Use only ORIGINAL_SOURCE below, not prior assistant claims as evidence. Return additions only, "
        "not explanations or duplicates. Empty candidates is valid. Select evidence IDs supplied by "
        "the program, never write offsets. Relations are not restricted to a fixed vocabulary. Preserve "
        "language, direction, numbers, negation and uncertainty. The output now uses the evidence envelope.\n"
        "ORIGINAL_SOURCE:\n" + json.dumps(evidence, ensure_ascii=False))
    query = e.request(f"A:{category}:round:{round_number}", prompt, schema, category,
                      parameters={"max_new_tokens": 4096, "temperature": 0.7})
    query["messages"] = deepcopy(history) + [{"role": "user", "content": query["prompt"]}]
    return query


def stop_request(category, history, round_number):
    query = e.request(f"A:{category}:stop:{round_number}",
        "Is another source-grounded extraction pass likely to find omitted " + category +
        " facts, including relations between existing entities or events? Do not treat more wording "
        "of the same facts as missing. Return continue_search and reason. This is a bounded "
        "self-check, not an external quality verdict.",
        r.obj({"continue_search": {"type": "boolean"}, "reason": {"type": "string"}}),
        category, {"max_new_tokens": 512, "temperature": 0.7})
    query["messages"] = deepcopy(history) + [{"role": "user", "content": query["prompt"]}]
    return query


def chunks(evidence, count=2):
    """Contiguous paragraph groups, zero overlap, all evidence exactly once."""
    e.validate_catalog(evidence)
    if type(count) is not int or count < 1:
        raise ValueError("Positive chunk count required")
    count = min(count, len(evidence))
    return [deepcopy(evidence[i*len(evidence)//count:(i+1)*len(evidence)//count]) for i in range(count)]


def chunk_requests(evidence, baseline, count=2):
    requests = []
    for index, group in enumerate(chunks(evidence, count), 1):
        for category in r.CATEGORIES:
            schema = r.obj({"candidates": r.array(e.candidate_schema(category, group))})
            requests.append(e.request(f"A_chunk:{index}:{category}",
                "Find additional source-supported facts of category " + category +
                " in this contiguous portion of the original source. Preserve source language, "
                "direction, qualifications and uncertainty. No relation vocabulary is imposed. "
                "Do not assert unresolved references. No overlap or outside knowledge. "
                "Return only additions to EXISTING, with source IDs. Empty is valid.\nSOURCE:\n" +
                json.dumps(group, ensure_ascii=False) + "\nEXISTING:\n" +
                json.dumps(baseline[c.CATEGORIES[category]], ensure_ascii=False), schema, category,
                {"max_new_tokens": 4096, "temperature": 0.7}))
    return requests


def completion_requests(inputs, evidence, max_nodes=2):
    """Retain measured focal-node coverage, replace fragile span strings with IDs."""
    drafts, coverage = old.nodewise_requests(inputs, max_nodes=max_nodes)
    queries = []
    for index, draft in enumerate(drafts):
        category = draft["category"]
        fields = deepcopy(e.candidate_schema(category, evidence, inferred=True)["properties"])
        fields["premise_ids"] = e.enum_array([x["id"] for x in inputs["items"]])
        schema = r.obj({"candidates": r.array(r.obj(fields))})
        prompt = (
            "Source-grounded graph completion: inspect the focal node and its incident graph. "
            "Propose missing connections involving that node, including connections to new "
            "source-supported nodes or another relation between existing ones. Use category " + category +
            ". No fixed relation/entity vocabulary. Do not replace the baseline, invent outside "
            "facts, or assume one relation per pair. Mark direct versus necessarily inferred facts. "
            "Select evidence_ids from SOURCE and optional premise_ids from GRAPH. IDs are sufficient, "
            "do NOT invent offsets or append :start:end. Native graph assertions alone are not proof. "
            "An empty candidates list is valid. Explain any inference briefly.\nFOCAL:\n" +
            json.dumps(draft["focal_node"], ensure_ascii=False) + "\nINCIDENT:\n" +
            json.dumps(draft["local_items"], ensure_ascii=False) + "\nGRAPH:\n" +
            json.dumps(inputs["items"], ensure_ascii=False) + "\nSOURCE:\n" + json.dumps(evidence, ensure_ascii=False))
        queries.append(e.request(f"K:{category}:{index:03d}", prompt, schema, category))
    return queries, coverage


def fusion_request(inputs, evidence):
    """Non-destructive alias/conflict audit, never a one-edge-per-pair merge."""
    ids = [x["id"] for x in inputs["items"]]
    pair = r.obj({"left_id": {"type": "string", "enum": ids},
                  "right_id": {"type": "string", "enum": ids},
                  "kind": {"type": "string", "enum": ["equivalent_claim", "contradictory_claim"]},
                  "evidence_ids": e.enum_array(sorted(e.validate_catalog(evidence)), 1),
                  "reason": {"type": "string", "minLength": 1}})
    return e.request("K:fusion_proposals",
        "Inspect this source-grounded graph for semantic duplicate claims or genuine contradictions. "
        "Only propose pairs from known item IDs. Similar topics, inverse word order or multiple "
        "relations alone are not contradictions. Check identity, roles, polarity, dates, quantities "
        "and scope in SOURCE. Do not merge nodes or remove assertions. The output is an audit "
        "proposal for independent checking, not a modification.\nGRAPH:\n" + json.dumps(inputs["items"], ensure_ascii=False) +
        "\nSOURCE:\n" + json.dumps(evidence, ensure_ascii=False), r.obj({"pairs": r.array(pair)}))


def fusion_verifier_request(proposals, inputs, evidence):
    lookup = {x["id"]: x for x in inputs["items"]}
    checked = []
    for index, pair in enumerate(proposals, 1):
        if pair["left_id"] == pair["right_id"] or not {pair["left_id"], pair["right_id"]} <= lookup.keys():
            continue
        checked.append({"id": f"fusion:{index}", "proposal": pair,
                        "left": lookup[pair["left_id"]], "right": lookup[pair["right_id"]]})
    if not checked:
        return None
    verdict = r.obj({"confirmed": {"type": "boolean"}, "reason": {"type": "string", "minLength": 1},
                     "evidence_ids": e.enum_array(sorted(e.validate_catalog(evidence)), 1)})
    return e.request("K:fusion_check", "Independently verify each proposed equivalence or contradiction "
        "against SOURCE. Require equal identities, direction, quantities, dates, polarity and scope "
        "for equivalence. A contradiction must be impossible jointly under the same scope, not "
        "merely different wording or relations. Uncertain means confirmed=false. No graph mutation.\nPAIRS:\n" +
        json.dumps(checked, ensure_ascii=False) + "\nSOURCE:\n" + json.dumps(evidence, ensure_ascii=False),
        r.obj({x["id"]: deepcopy(verdict) for x in checked}))
