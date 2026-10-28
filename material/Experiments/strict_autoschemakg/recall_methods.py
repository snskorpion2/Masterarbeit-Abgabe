"""Pure recall interventions. No model calls, task-specific facts or judge feedback."""
from __future__ import annotations

from copy import deepcopy
import json
import re
import unicodedata

from . import reliability_v2 as r

ARM_ORDER = ("baseline", "glean", "anchors", "decomposition", "all")
EXTRACTION_PARAMETERS = {"max_new_tokens": 2048, "temperature": 0.7, "do_sample": True,
                         "repetition_penalty": 1.0, "return_full_text": False,
                         "truncation": True, "padding": False}


def normalize(text):
    return re.sub(r"\s+", " ", text).strip()


def source_units(source):
    """Freeze all nonempty paragraphs, including headings, without dropping text."""
    units = [{"id": f"U{index:04d}", "text": normalize(part)}
             for index, part in enumerate((x for x in re.split(r"\n\s*\n", source)
                                           if x.strip()), 1)]
    if not units or " ".join(x["text"] for x in units) != normalize(source):
        raise ValueError("Source units do not cover the complete normalized source")
    return units


def _units(units):
    if (not units or any(set(x) != {"id", "text"} or not isinstance(x["id"], str)
                        or not x["id"] or not isinstance(x["text"], str) or not x["text"].strip()
                        for x in units) or len({x["id"] for x in units}) != len(units)):
        raise ValueError("Source units require unique IDs and nonempty source text")
    return {x["id"]: x["text"] for x in units}


def preprocessing_request(units):
    _units(units)
    statements = r.array({"type": "string", "minLength": 1})
    statements["minItems"] = 1
    prompt = (
        "METHOD: source-preserving sentence decomposition and coreference resolution.\n"
        "For EVERY source unit, return an array of simpler atomic statements. Resolve pronouns and "
        "references only when the source makes their antecedents clear. Preserve all stated facts, "
        "qualifiers, dates, numbers, negation and uncertainty. Do not summarize, add facts, infer new "
        "relations or omit headings or difficult material. If resolution is uncertain, preserve the "
        "original wording. Use surrounding source units only to resolve references. Keep each statement "
        "under the ID of the original unit it represents. Return exactly the required JSON object, "
        "one nonempty statement array per source ID, without other keys.\nSOURCE_UNITS:\n"
        + json.dumps(units, ensure_ascii=False))
    return {"request_id": "shared:preprocessing", "kind": "recall_preprocess", "item_ids": list(_units(units)),
            "source_units": units, "prompt": prompt,
            "output_schema": r.obj({x["id"]: deepcopy(statements) for x in units}),
            "parameters": {**EXTRACTION_PARAMETERS, "max_new_tokens": 8192}}


def anchor_request(units):
    ids = list(_units(units))
    anchor = r.obj({"source_unit_id": {"type": "string", "enum": ids},
                    "kind": {"type": "string", "enum": ["entity", "relation", "value"]},
                    "text": {"type": "string", "minLength": 1},
                    "quote": {"type": "string", "minLength": 1}})
    prompt = (
        "METHOD: source anchor inventory, without a predefined ontology.\n"
        "Identify source-grounded entities, relation expressions and values (including dates and numbers). "
        "For each anchor return its source_unit_id, kind (entity, relation or value), text, and an exact "
        "verbatim quote from that original source unit. The anchor text must occur verbatim in its quote. "
        "Do not invent, paraphrase or normalize quotes or anchor text. These are coverage hints, not "
        "verified missing facts or a relation schema. Return exactly {\"anchors\": [...]} with these "
        "four fields per anchor. An empty array is valid when no anchors are found.\nSOURCE_UNITS:\n"
        + json.dumps(units, ensure_ascii=False))
    return {"request_id": "shared:anchors", "kind": "recall_anchors", "item_ids": ids,
            "source_units": units, "prompt": prompt, "output_schema": r.obj({"anchors": r.array(anchor)}),
            "parameters": {**EXTRACTION_PARAMETERS, "max_new_tokens": 4096}}


def validate_response(request, value):
    """Check source binding in addition to JSON schema, without claiming factual truth."""
    units = _units(request["source_units"])
    if request["kind"] == "recall_preprocess":
        if set(value) != set(units) or any(not statements or any(not x.strip() for x in statements)
                                          for statements in value.values()):
            raise ValueError("Incomplete source-unit decomposition")
    elif request["kind"] == "recall_anchors":
        for anchor in value["anchors"]:
            quote, text = anchor["quote"], anchor["text"]
            if (anchor["source_unit_id"] not in units or not quote.strip() or not text.strip()
                    or quote not in units[anchor["source_unit_id"]] or text not in quote):
                raise ValueError("Anchor lacks an exact original-source quotation")
    else:
        raise ValueError("Unknown recall response contract")
    return value


def resolved_view(units, response):
    request = preprocessing_request(units)
    r.validate(response, request["output_schema"])
    validate_response(request, response)
    return "\n".join(statement for unit in units for statement in response[unit["id"]])


def extraction_requests(view, prefix):
    return [{"request_id": f"{prefix}:extraction:{category}", "kind": "extraction",
             "category": category, "item_ids": [], "messages": messages,
             "prompt": messages[-1]["content"], "parameters": dict(EXTRACTION_PARAMETERS)}
            for category, messages in zip(r.CATEGORIES, r.native_extraction_prompts(view))]


def _lexical_match(needle, text):
    """Exact case-sensitive occurrence bounded by Unicode letters/numbers/marks."""
    def lexical(char):
        return unicodedata.category(char)[0] in "LNM"
    start = text.find(needle)
    while needle and start >= 0:
        end = start + len(needle)
        if (start == 0 or not lexical(text[start - 1])) and (end == len(text) or not lexical(text[end])):
            return True
        start = text.find(needle, start + 1)
    return False


def unused_anchors(anchors, triples, *, deterministic_repairs=False):
    """Case-sensitive lexical diagnostic only, never a semantic coverage decision."""
    strings = []
    for triple in triples:
        for value in triple.values():
            strings.extend(value if isinstance(value, list) else [value])
    match = _lexical_match if deterministic_repairs else lambda needle, text: needle in text
    return [deepcopy(anchor) for anchor in anchors if not any(match(anchor["text"], text) for text in strings)]


def supplement_requests(source, state, method, prefix, anchors=None, *, deterministic_repairs=False):
    if method not in {"glean", "anchors"}:
        raise ValueError("Unknown recall supplement")
    result = []
    for category in r.CATEGORIES:
        existing = state["triples"][category]
        hints = unused_anchors(anchors or [], existing, deterministic_repairs=deterministic_repairs) if method == "anchors" else []
        native = r.native_extraction_prompts(source)[r.CATEGORIES.index(category)]
        instruction = (
            f"METHOD: {method}. One additional extraction pass for this triple type only.\n"
            "Apply the original extraction definitions below. Read the entire original source and the "
            "existing output. Return only additional source-supported statements absent from the existing "
            "output. Do not rewrite, remove or correct existing statements. Do not invent facts. Return "
            "the same JSON array format, or [] if nothing can be added.\n")
        if method == "anchors":
            instruction += ("The unused anchors below are exact lexical hints, not proof of missing facts or "
                            "incorrect extraction. They do not define an ontology. Use them to inspect the "
                            "source, never force a relation merely to consume an anchor.\nUNUSED_ANCHORS:\n"
                            + json.dumps(hints, ensure_ascii=False) + "\n")
        prompt = (instruction + "EXISTING_OUTPUT:\n" + json.dumps(existing, ensure_ascii=False)
                  + "\nORIGINAL_EXTRACTION_TASK_AND_SOURCE:\n" + native[-1]["content"])
        request = {"request_id": f"{prefix}:{method}:{category}", "kind": "extraction",
                   "category": category, "item_ids": [], "prompt": prompt,
                   "messages": [native[0], {"role": "user", "content": prompt}],
                   "parameters": dict(EXTRACTION_PARAMETERS), "method": method}
        if method == "anchors":
            request["unused_anchors"] = hints
            if deterministic_repairs:
                request["anchor_match_protocol"] = "case_sensitive_unicode_LNM_boundaries_v1_lexical_hint_only"
        result.append(request)
    return result


def _validated_results(schedule, results, *, allow_partial=False):
    if len(schedule) != 3 or len(results) != 3 or [x["category"] for x in schedule] != list(r.CATEGORIES):
        raise ValueError("Expected exactly one result per EE/EV/VV category in order")
    if allow_partial and (len({q["request_id"] for q in schedule}) != 3 or any(
            result.get("request_id") != query["request_id"] for query, result in zip(schedule, results))):
        raise ValueError("Partial supplement results do not match unique scheduled request IDs")
    for request, result in zip(schedule, results):
        if result["status"] != "valid":
            if allow_partial:
                continue
            raise ValueError("Cannot use an invalid extraction")
        r.validate(result["parsed"], r.schema_for(request))
        yield request, result["parsed"]


def extraction_state(schedule, results):
    state = {"triples": {}, "provenance": {}}
    for request, values in _validated_results(schedule, results):
        category = request["category"]
        state["triples"][category] = deepcopy(values)
        # Retain every base occurrence, including base duplicates, exactly as generated.
        state["provenance"][category] = [[{"request_id": request["request_id"], "value": deepcopy(value)}]
                                          for value in values]
    return state


def merge_additions(base, schedule, results, *, deterministic_repairs=False):
    state = deepcopy(base)
    for request, additions in _validated_results(schedule, results, allow_partial=deterministic_repairs):
        category = request["category"]
        existing, provenance = state["triples"][category], state["provenance"][category]
        for value in additions:
            origin = {"request_id": request["request_id"], "value": deepcopy(value)}
            index = next((i for i, item in enumerate(existing)
                          if (item["Event"] == value["Event"] if category == "event" else item == value)), None)
            if index is None:
                existing.append(deepcopy(value))
                provenance.append([origin])
            else:
                if category == "event":
                    for entity in value["Entity"]:
                        if entity not in existing[index]["Entity"]:
                            existing[index]["Entity"].append(entity)
                if origin not in provenance[index]:
                    provenance[index].append(origin)
    if deterministic_repairs:
        state.setdefault("supplement_status", []).append({
            "complete": all(row["status"] == "valid" for row in results),
            "categories": [{"category": query["category"], "request_id": query["request_id"],
                            "status": row["status"], "merged": row["status"] == "valid"}
                           for query, row in zip(schedule, results)]})
    return state


def extraction_row(state, source):
    return {"id": "recall-source", "original_text": source,
            **{field: deepcopy(state["triples"][category]) for category, field in zip(r.CATEGORIES, r.FIELDS)}}


def confidence_items(inventory, state, producers):
    """Bind every final item/link to the actual source requests, including EV unions."""
    result = []
    for item in inventory["items"]:
        category = "event" if item["category"] == "event_entity_link" else item["category"]
        origins = state["provenance"][category][item["item_index"]]
        if item["category"] == "event_entity_link":
            origins = [x for x in origins if item["value"]["Entity"] in x["value"]["Entity"]]
        ids = list(dict.fromkeys(x["request_id"] for x in origins))
        if not ids or any(ident not in producers for ident in ids):
            raise ValueError("Final extraction item lacks known producer provenance")
        inputs = [r._request_messages(producers[ident]["request"]) for ident in ids]
        responses = [producers[ident]["result"]["raw_response"] for ident in ids]
        result.append({"id": item["occurrence_id"], "event": "extraction",
                       "original_input": inputs[0] if len(inputs) == 1 else inputs,
                       "original_response": responses[0] if len(responses) == 1 else responses,
                       "focal_stored_item": item["value"], "producer_request_ids": ids,
                       "producer_index": r.artifacts.digest(ids), "producer_origins": deepcopy(origins)})
    return result
