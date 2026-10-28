"""Opt-in, versioned technical repairs; historical request builders stay unchanged."""
from __future__ import annotations

from copy import deepcopy
from contextlib import contextmanager
from contextvars import ContextVar
from decimal import Decimal
import json

PROMPT_PROTOCOL = "lossless_prompt_projection_v1"
ADAPTIVE_PROTOCOL = "adaptive_output_budget_v1"
MISSING_PROTOCOL = "exact_native_missing_consistency_v1"
GROUNDED_WHITESPACE_PROTOCOL = "grounded_json_whitespace_projection_v1"
MAX_ADAPTIVE_OUTPUT = 8192
ADAPTIVE_PROTOCOL_V2 = "adaptive_output_budget_v2"
ADAPTIVE_CEILINGS = (8192, 16384, 32768)
OUTPUT_SAFETY_TOKENS = 256
_active_ceiling = ContextVar("adaptive_output_ceiling_v2", default=None)


@contextmanager
def output_ceiling_scope(ceiling):
    if ceiling is not None and (type(ceiling) is not int or ceiling not in ADAPTIVE_CEILINGS):
        raise ValueError("Unsupported adaptive output ceiling")
    token = _active_ceiling.set(ceiling)
    try:
        yield
    finally:
        _active_ceiling.reset(token)


def active_output_ceiling():
    return _active_ceiling.get()


def _replace_labeled(prompt, label, old, new, what):
    if prompt.count(label) != 1:
        raise ValueError(f"Cannot locate unique {what} label in frozen prompt")
    start = prompt.index(label) + len(label)
    if not prompt.startswith(old, start):
        raise ValueError(f"Frozen {what} differs from stored data")
    return prompt[:start] + new + prompt[start + len(old):]


def _grounded_json_pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate grounded JSON key")
        result[key] = value
    return result


def _grounded_json_constant(_):
    raise ValueError("Nonfinite grounded JSON constant")


def _grounded_metadata(value):
    if type(value) is dict:
        if any(type(key) is not str for key in value):
            raise ValueError("Grounded metadata keys must be strings")
        for child in value.values():
            _grounded_metadata(child)
    elif type(value) is list:
        for child in value:
            _grounded_metadata(child)
    elif value is not None and type(value) not in (str, int, float, bool):
        raise ValueError("Expected JSON-native grounded metadata")
    # In particular, reject NaN/Infinity in Python metadata as well as in text.
    json.dumps(value, allow_nan=False)


def _grounded_json_section(prompt, label, decoder):
    marker = "\n" + label + ":\n"
    if prompt.count(marker) != 1:
        raise ValueError("Expected unique grounded JSON section: " + label)
    start = prompt.index(marker) + len(marker)
    value, size = decoder.raw_decode(prompt[start:])
    return start, start + size, prompt[start:start + size], value


def _grounded_json_same(left, right):
    if type(left) is not type(right):
        return False
    if type(left) is dict:
        return left.keys() == right.keys() and all(_grounded_json_same(left[k], right[k]) for k in left)
    if type(left) is list:
        return len(left) == len(right) and all(_grounded_json_same(a, b) for a, b in zip(left, right))
    return left == right


def _grounded_json_whitespace(raw):
    result, quoted, escaped = [], False, False
    for char in raw:
        if quoted:
            result.append(char)
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                quoted = False
        elif char == '"':
            quoted = True
            result.append(char)
        elif char not in " \t\r\n":
            result.append(char)
    return "".join(result)


def compact_grounded_requests(schedule):
    """Opt-in JSON whitespace only for the three known grounded K/B layouts.

    No aliases, fields, string/number lexemes or source sections are removed.
    This changes prompt bytes, not the output schema or generation limits. It
    proves neither native token savings, context fit nor extraction quality.
    Other grounded layouts fail closed rather than guessing JSON boundaries.
    """
    if type(schedule) not in (list, tuple):
        raise ValueError("Expected a grounded request schedule")
    required = {"request_id", "kind", "category", "prompt", "output_schema", "parameters"}
    allowed = required | {"messages", "prompt_projection_protocol"}
    labels = ("FOCAL", "INCIDENT", "GRAPH", "SOURCE", "CANDIDATES", "ORIGINAL_SOURCE",
              "ELEMENT_MAPPINGS", "OUTPUT_CONTRACT (JSON only)")
    contract = labels[-1]
    layouts = (("FOCAL", "INCIDENT", "GRAPH", "SOURCE", contract),
               ("GRAPH", "SOURCE", contract),
               ("CANDIDATES", "ORIGINAL_SOURCE", "ELEMENT_MAPPINGS", contract))
    decoder = json.JSONDecoder(object_pairs_hook=_grounded_json_pairs,
                               parse_constant=_grounded_json_constant, parse_float=Decimal)
    result = deepcopy(schedule)
    for request in result:
        if (type(request) is not dict or not required <= request.keys() or not request.keys() <= allowed or
                type(request["kind"]) is not str or request["kind"] != "grounded_method_v1" or
                type(request["category"]) is not str or request["category"] not in ("entity", "event", "relation") or
                type(request["request_id"]) is not str or not request["request_id"] or
                type(request["prompt"]) is not str or not request["prompt"] or
                type(request["output_schema"]) is not dict or type(request["parameters"]) is not dict or
                type(request["parameters"].get("max_new_tokens")) is not int or
                request["parameters"]["max_new_tokens"] <= 0 or
                type(request.get("prompt_projection_protocol", GROUNDED_WHITESPACE_PROTOCOL)) is not str or
                request.get("prompt_projection_protocol", GROUNDED_WHITESPACE_PROTOCOL) != GROUNDED_WHITESPACE_PROTOCOL):
            raise ValueError("Invalid grounded request metadata")
        _grounded_metadata(request["output_schema"])
        _grounded_metadata(request["parameters"])
        prompt = request["prompt"]
        messages = request.get("messages")
        if "messages" in request and (type(messages) is not list or not messages or any(
                type(message) is not dict or set(message) != {"role", "content"} or
                type(message["role"]) is not str or message["role"] not in ("system", "user", "assistant") or
                type(message["content"]) is not str
                for message in messages) or messages[-1]["role"] != "user" or messages[-1]["content"] != prompt):
            raise ValueError("Grounded messages differ from prompt")
        present = sorted((prompt.index("\n" + label + ":\n"), label) for label in labels
                         if "\n" + label + ":\n" in prompt)
        layout = tuple(label for _, label in present)
        if layout not in layouts:
            raise ValueError("Unknown grounded JSON section layout")
        sections = {label: _grounded_json_section(prompt, label, decoder) for label in layout}
        for index, label in enumerate(layout):
            _, end, _, value = sections[label]
            expected_type = dict if label in ("FOCAL", contract) else list
            if type(value) is not expected_type:
                raise ValueError("Wrong grounded JSON section type: " + label)
            if index + 1 < len(layout):
                next_marker = "\n" + layout[index + 1] + ":\n"
                gap = prompt[end:present[index + 1][0]]
                if label != "ORIGINAL_SOURCE" and gap:
                    raise ValueError("Unexpected text after grounded JSON section: " + label)
                if label == "ORIGINAL_SOURCE" and not gap.startswith("\nADDITIONAL ANCHORED-EXTRACTION CHECK: "):
                    raise ValueError("Missing anchored-verifier format boundary")
                if not prompt.startswith(next_marker, present[index + 1][0]):
                    raise ValueError("Grounded section boundary changed")
            elif prompt[end:].strip(" \t\r\n"):
                raise ValueError("Trailing material after grounded output contract")
        schema = decoder.decode(json.dumps(request["output_schema"], ensure_ascii=False, allow_nan=False))
        if not _grounded_json_same(sections[contract][3], schema):
            raise ValueError("Grounded output contract differs from stored schema")
        for label in layout:
            if label in ("SOURCE", "ORIGINAL_SOURCE"):
                continue
            raw = sections[label][2]
            compact = _grounded_json_whitespace(raw)
            if not _grounded_json_same(decoder.decode(compact), sections[label][3]):
                raise ValueError("Grounded JSON projection changed values")
            prompt = _replace_labeled(prompt, "\n" + label + ":\n", raw, compact, "grounded " + label)
        request["prompt"] = prompt
        if messages is not None:
            # A repeated dict object in history must not rewrite earlier turns.
            messages[-1] = {**messages[-1], "content": prompt}
        request["prompt_projection_protocol"] = GROUNDED_WHITESPACE_PROTOCOL
    return result


def compact_completion_requests(schedule):
    """Remove only repeated provenance aliases from the transmitted item JSON."""
    result = deepcopy(schedule)
    for request in result:
        if request.get("kind") != "completion" or "baseline_items" not in request:
            raise ValueError("Expected completion request with frozen baseline items")
        if "messages" in request:
            raise ValueError("Completion prompt projection requires a message-less request")
        items = request["baseline_items"]
        projected = [{key: value for key, value in item.items()
                      if key != "origin_item_id" or value != item.get("id")}
                     for item in items]
        old = json.dumps(items, ensure_ascii=False)
        new = json.dumps(projected, ensure_ascii=False, separators=(",", ":"))
        request["prompt"] = _replace_labeled(request["prompt"], "BASELINE_ITEMS:\n", old, new,
                                              "baseline items")
        request["prompt_projection_protocol"] = PROMPT_PROTOCOL
    return result


def compact_anchor_supplements(schedule):
    """Remove only quotes identical to anchor text in transmitted hints."""
    result = deepcopy(schedule)
    for request in result:
        if request.get("method") != "anchors" or "unused_anchors" not in request:
            raise ValueError("Expected anchor supplement with frozen hints")
        messages = request.get("messages")
        if (not isinstance(messages, list) or not messages or not isinstance(messages[-1], dict) or
                messages[-1].get("role") != "user" or
                messages[-1].get("content") != request["prompt"]):
            raise ValueError("Anchor supplement messages differ from frozen prompt")
        hints = request["unused_anchors"]
        projected = [{key: value for key, value in item.items()
                      if key != "quote" or value != item.get("text")}
                     for item in hints]
        old = json.dumps(hints, ensure_ascii=False)
        new = json.dumps(projected, ensure_ascii=False, separators=(",", ":"))
        request["prompt"] = _replace_labeled(request["prompt"], "UNUSED_ANCHORS:\n", old, new,
                                              "anchor hints")
        request["messages"][-1]["content"] = request["prompt"]
        request["prompt_projection_protocol"] = PROMPT_PROTOCOL
    return result


def enable_adaptive_output(schedule):
    """Opt in per request; initial generation parameters are not changed."""
    result = deepcopy(schedule)
    for request in result:
        initial = request.get("parameters", {}).get("max_new_tokens")
        if type(initial) is not int or not 0 < initial <= MAX_ADAPTIVE_OUTPUT:
            raise ValueError("Adaptive output needs an explicit initial limit at most 8192")
        request["adaptive_output_protocol"] = ADAPTIVE_PROTOCOL
    return result


def enable_adaptive_output_v2(schedule, *, ceiling=16384):
    """Freeze a separate policy and ceiling on every request, without altering input."""
    if type(ceiling) is not int or ceiling not in ADAPTIVE_CEILINGS:
        raise ValueError("Unsupported adaptive output ceiling")
    result = deepcopy(schedule)
    for request in result:
        initial = request.get("parameters", {}).get("max_new_tokens")
        if type(initial) is not int or not 0 < initial <= MAX_ADAPTIVE_OUTPUT:
            raise ValueError("Adaptive output needs an explicit initial limit at most 8192")
        request["adaptive_output_protocol"] = ADAPTIVE_PROTOCOL_V2
        request["adaptive_output_ceiling"] = ceiling
    return result


def effective_output_budget(request, previous_attempt, context):
    """Return the next exact cap from the last frozen outcome, without guessing tokens."""
    protocol = request.get("adaptive_output_protocol")
    if protocol not in (ADAPTIVE_PROTOCOL, ADAPTIVE_PROTOCOL_V2):
        raise ValueError("Unknown or disabled adaptive output protocol")
    if type(context) is not int or context <= 0:
        raise ValueError("Invalid verified context")
    if protocol == ADAPTIVE_PROTOCOL_V2:
        ceiling = request.get("adaptive_output_ceiling")
        if type(ceiling) is not int or ceiling not in ADAPTIVE_CEILINGS:
            raise ValueError("Missing or invalid adaptive output ceiling")
        safety = OUTPUT_SAFETY_TOKENS
    else:
        ceiling, safety = MAX_ADAPTIVE_OUTPUT, 0
    initial = request["parameters"]["max_new_tokens"]
    if type(initial) is not int or not 0 < initial <= MAX_ADAPTIVE_OUTPUT:
        raise ValueError("Invalid initial output budget")
    if previous_attempt is None:
        return initial
    prior = previous_attempt["effective_max_new_tokens"]
    if type(prior) is not int or not 0 < prior <= ceiling:
        raise ValueError("Previous effective output budget is invalid")
    if previous_attempt["status"] != "length_abort":
        return prior
    prompt_tokens = previous_attempt.get("usage", {}).get("prompt_eval_count")
    if type(prompt_tokens) is not int or not 0 <= prompt_tokens < context:
        raise ValueError("Length abort lacks measured prompt token count")
    remaining = context - prompt_tokens - safety
    if remaining < prior:
        raise ValueError("Previous output budget exceeded measured free context")
    if protocol == ADAPTIVE_PROTOCOL_V2:
        output_tokens = previous_attempt.get("usage", {}).get("eval_count")
        if type(output_tokens) is not int or output_tokens != prior:
            raise ValueError("Length abort lacks coherent measured output count")
        if previous_attempt.get("verified_length_abort") is not True:
            raise ValueError("Length abort lacks verified transport evidence")
    return min(prior * 2, ceiling, remaining)


def enable_missing_consistency(schedule, inventory):
    """Bind judge-more requests to exact native units without changing prompts."""
    values = {"entity": [], "event": [], "relation": []}
    for item in inventory["items"]:
        category = item["category"]
        if category == "event_entity_link":
            value = item["value"]
            values["event"].append([value["Event"], value["Entity"]])
        elif category in ("entity", "relation"):
            value = item["value"]
            values[category].append([value["Head"], value["Relation"], value["Tail"]])
    result = deepcopy(schedule)
    for request in result:
        if request.get("kind") == "more":
            category = request["category"]
            request["missing_consistency_protocol"] = MISSING_PROTOCOL
            request["existing_native_units"] = deepcopy(values[category])
    return result
