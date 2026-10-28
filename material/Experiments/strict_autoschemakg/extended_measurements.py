"""Exploratory sidecar prompts and strict response contracts, never native metrics."""
from __future__ import annotations

import json
import math
import re

from .contract import parse_json
from .evaluation import load_native
from .contract import DEFAULT_SOURCE

CONFIDENCE_TARGETS = {
    "extraction": "Is the exact stored extracted triple or EV participation supported by the source?",
    "induction": "Is this specific stored object-to-concept mapping appropriate?",
    "native_triple_judgment": "Was your already issued native triple judgment correct as a judgment, not merely is the fact plausible?",
    "id_triple_judgment": "Was your already issued triple judgment correct as a judgment, not merely is the fact plausible?",
    "mcq_answer": "Is the A-D answer you selected correct?",
    "mcq_abstention": "Was choosing E appropriate because your answer confidence was insufficient?",
}
FENCE = re.compile(r"\A[ \t\r\n]*```(?:json)?\r?\n(?P<body>[\s\S]*?)\r?\n```[ \t\r\n]*\Z")
E_RULE = ("E. I am not sufficiently confident to answer.\n\n"
          "Please select A, B, C, or D only if sufficiently confident in your answer. "
          "Otherwise select E. Respond with only the letter of your choice.\n")


def parse_json_response(raw):
    if not isinstance(raw, str) or not raw.strip():
        raise ValueError("Empty response")
    match = FENCE.fullmatch(raw)
    if "```" in raw and match is None:
        raise ValueError("Incomplete or additional JSON fence")
    value = parse_json(match["body"] if match else raw)
    if isinstance(value, list):
        if not all(isinstance(item, dict) for item in value):
            raise ValueError("JSON judgment array must contain only objects")
        # Sidecar-only container bridge; preserve every parsed judgment unchanged.
        return {"judgments": value}
    if not isinstance(value, dict):
        raise ValueError("JSON response must be an object")
    return value


def _judgments(response, ids):
    items = response.get("judgments")
    if not isinstance(items, list) or len(items) != len(ids) or len(ids) != len(set(ids)):
        raise ValueError("Missing or duplicate judgment IDs")
    found = [item.get("id") if isinstance(item, dict) else None for item in items]
    if found != ids:
        raise ValueError("Judgments must contain exactly the requested IDs in order")
    return items


def validate_confidence(response, ids):
    result = []
    for item in _judgments(response, ids):
        score = item.get("confidence_score")
        if type(score) not in (int, float) or not math.isfinite(score) or not 0 <= score <= 10:
            raise ValueError("confidence_score must be a finite 0-10 number, not Boolean")
        result.append({"id": item["id"], "confidence_score": score,
                       "confidence_normalized": score / 10})
    return result


def confidence_container(response, ids, *, allow_id_reorder=False):
    """Lossless containers; complete ID reordering requires explicit v2 opt-in."""
    value = response.get("judgments", response)
    if (len(ids) == 1 and response.get("id") == ids[0]
            and set(response) == {"id", "confidence_score"}):
        wrapped = {"judgments": [response]}
        validate_confidence(wrapped, ids)
        return wrapped, "exact_singleton"
    if isinstance(value, list):
        if allow_id_reorder:
            if (set(response) != {"judgments"} or len(value) != len(ids)
                    or not all(isinstance(ident, str) for ident in ids)
                    or len(ids) != len(set(ids))
                    or not all(isinstance(item, dict) and set(item) == {"id", "confidence_score"}
                               and isinstance(item["id"], str) for item in value)):
                raise ValueError("ID reorder requires complete, exact confidence objects")
            found = [item["id"] for item in value]
            if len(found) != len(set(found)) or set(found) != set(ids):
                raise ValueError("ID reorder requires each expected ID exactly once")
            by_id = {item["id"]: item for item in value}
            ordered = {"judgments": [by_id[ident] for ident in ids]}
            validate_confidence(ordered, ids)
            if found != ids:
                return ordered, "exact_id_reorder"
        return response, None
    if not isinstance(value, dict) or set(value) != set(ids) or len(ids) != len(set(ids)):
        raise ValueError("Confidence map must contain exactly the requested IDs")
    if "judgments" in response and set(response) != {"judgments"}:
        raise ValueError("Unexpected confidence container fields")
    items = []
    for ident in ids:
        entry = value[ident]
        if isinstance(entry, dict):
            if set(entry) - {"id", "confidence_score"} or entry.get("id", ident) != ident:
                raise ValueError("Conflicting ID or extra confidence fields")
            item = {"id": ident, **entry}
        else:
            item = {"id": ident, "confidence_score": entry}
        items.append(item)
    return {"judgments": items}, "exact_id_map"


def confidence_prompt(item_id, event, original_input, original_response):
    return confidence_batch_prompt([{"id": item_id, "event": event,
                                     "original_input": original_input,
                                     "original_response": original_response}])


def confidence_batch_prompt(items):
    if not items or len({x["id"] for x in items}) != len(items):
        raise ValueError("Confidence batch IDs must be unique")
    serialized = [dict(item) for item in items]
    for item in serialized:
        item["confidence_target"] = CONFIDENCE_TARGETS[item["event"]]
    common = {}
    sources = [x.get("original_input", {}).get("source")
               if isinstance(x.get("original_input"), dict) else None for x in serialized]
    if sources[0] is not None and all(source == sources[0] for source in sources):
        common["shared_source"] = sources[0]
        for item in serialized:
            item["original_input"] = {key: value for key, value in item["original_input"].items()
                                      if key != "source"} | {"source_ref": "shared_source"}
    inputs = [x["original_input"] for x in serialized]
    outputs = [x["original_response"] for x in serialized]
    if len(serialized) > 1 and all(value == inputs[0] for value in inputs) and all(value == outputs[0] for value in outputs):
        common["shared_original_input"] = inputs[0]
        common["shared_original_response"] = outputs[0]
        for item in serialized:
            item["original_input"] = {"ref": "shared_original_input"}
            item["original_response"] = {"ref": "shared_original_response"}
    return ("Post-hoc self-reported confidence only. Do not revise the stored answer. "
            "How reliable is your own prior result for the indicated item/event? "
            "Use confidence_score on a fixed 0-10 scale, where 0 is no confidence and 10 is maximal confidence. "
            "Return exactly one JSON object with judgments in input order, each containing only "
            "id and confidence_score. No calibration or correctness claim is implied.\n"
            "Prior items (full input and response, no truncation; shared values are referenced losslessly):\n"
            + json.dumps({"common": common, "items": serialized}, ensure_ascii=False, allow_nan=False))


def answer_prompt(question, contexts, variant):
    native = load_native(DEFAULT_SOURCE, "InfoPreservation/answer_generation.py")
    options = question["options"]
    prompt = native.MCQ_ANSWER_PROMPT.format(contexts=contexts, question=question["question"],
                                              options_0=options[0], options_1=options[1],
                                              options_2=options[2], options_3=options[3])
    if variant == "ad":
        return prompt
    if variant != "ae":
        raise ValueError("Unknown MCQ variant")
    return prompt.replace("\nPlease select the correct answer by choosing A, B, C, or D. Respond with only the letter of your choice.\n",
                          "\n" + E_RULE)


def parse_answer(raw, variant):
    if not isinstance(raw, str) or not re.fullmatch(r"[ \t\r\n]*[A-D" + ("E" if variant == "ae" else "") + r"][ \t\r\n]*", raw):
        return None
    return raw.strip()
