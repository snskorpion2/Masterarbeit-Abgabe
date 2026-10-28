"""Opt-in, source-grounded temporal compiler with no dispatch or file writes.

Natural-language interpretation belongs to the proposer and independent source
verifier, not to English lexical heuristics. Binding, verifier support, formal
consistency and proof validity are deliberately separate. A verifier can err.
Old temporal compiler contracts and frozen artifacts are not modified.
"""
from __future__ import annotations

from calendar import monthrange
from copy import deepcopy
from datetime import date
import json

import jsonschema

from .contract import parse_json
from . import temporal_reasoner as reasoner
from . import compiler_conflict_diagnostics_v1 as conflict

PROTOCOL = "compiler_grounded_v3"
VERIFY_PROTOCOL = PROTOCOL + "_source_verifier"
LOCAL_POLICY = "asserted_dependencies_v1"
WHOLE_POLICY = "whole_component_v1"
MAX_REPAIRS = 3
DECISIONS = ("supported", "contradicted", "insufficient")


def _require(condition, message):
    if not condition:
        raise ValueError(message)


def _obj(properties):
    return {"type": "object", "properties": properties, "required": list(properties),
            "additionalProperties": False}


def _array(items, *, minimum=0, unique=False):
    return {"type": "array", "items": items, "minItems": minimum, "uniqueItems": unique}


def _enum(values):
    return {"type": "string", "enum": list(values)}


def _text():
    return {"type": "string", "minLength": 1}


def _dump(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, allow_nan=False)


def _inputs(events, catalog):
    _require(isinstance(events, list) and events, "At least one dynamic input event is required")
    _require(isinstance(catalog, list) and catalog, "A direct source evidence catalog is required")
    for event in events:
        _require(isinstance(event, dict) and set(event) == {"id", "text"}
                 and all(isinstance(event[key], str) and event[key].strip() for key in event), "Invalid event record")
    previous_end = 0
    for entry in catalog:
        _require(isinstance(entry, dict) and set(entry) == {"id", "text", "start", "end"}, "Invalid source catalog record")
        _require(isinstance(entry["id"], str) and entry["id"].strip()
                 and isinstance(entry["text"], str) and entry["text"].strip(), "Empty source evidence")
        _require(type(entry["start"]) is int and type(entry["end"]) is int
                 and previous_end <= entry["start"] < entry["end"] and entry["end"] - entry["start"] == len(entry["text"]),
                 "Source evidence offsets must address the exact Unicode text")
        previous_end = entry["end"]
    _require(len({e["id"] for e in events}) == len(events), "Duplicate event ID")
    _require(len({e["id"] for e in catalog}) == len(catalog), "Duplicate evidence ID")


def formalization_request(events, source_catalog, *, request_id="compiler-grounded:0"):
    _inputs(events, source_catalog)
    prompt = (
        "Formalize only source-supported temporal facts about the supplied native events. "
        "SOURCE_CATALOG is the original evidence, NATIVE_EVENTS may contain extraction errors. "
        "Interpret the source in its own language. Never rely on English keyword rules. "
        "Keep event text in the source language. Use ONLY supplied parent event IDs and evidence IDs. "
        "Return an entry for EVERY parent event ID. An unsupported event is unformalized with subevents=[]. "
        "Split a compound native event into distinct ATOMIC subevents only when the original source "
        "explicitly supports distinct activities. Use unique local_id values within each parent. "
        "Do not invent events to resolve a contradiction. A single activity over a range is ONE "
        "subevent with ONE interval, never two point events for the interval endpoints. "
        "Preserve polarity, assertion status and modality explicitly. A year in a name or title is "
        "not an event date. date_role must distinguish this. Translate dates to conservative ISO "
        "YYYY-MM-DD earliest_start/latest_end bounds, preserving full year/month uncertainty. "
        "For unknown or ambiguous dates use status unknown/ambiguous, empty bound strings and "
        "precision unknown. Never guess a locale, year, missing endpoint or temporal order. "
        "Orders are explicit before/after assertions, not causal relations or inferred date comparisons. "
        "Reference the exact parent event_id and local_id of each endpoint in this response. "
        "Evidence IDs cite verbatim original catalog entries. An evidence ID alone is not proof "
        "that the interpretation is correct. Return JSON only matching OUTPUT_SCHEMA.\n"
        "NATIVE_EVENTS:\n" + _dump(events) + "\nSOURCE_CATALOG:\n" + _dump(source_catalog))
    request = {"request_id": request_id, "kind": PROTOCOL, "protocol": PROTOCOL,
               "item_ids": [e["id"] for e in events], "events": deepcopy(events),
               "source_catalog": deepcopy(source_catalog), "parameters": {"max_new_tokens": 4096}}
    request["input_sha256"] = reasoner._digest({"events": events, "source_catalog": source_catalog})
    request["prompt"] = prompt + "\nOUTPUT_SCHEMA:\n" + _dump(schema_for(request))
    request["messages"] = [{"role": "user", "content": request["prompt"]}]
    return request


def formalization_requests(events, source_catalog, *, max_events_per_request=12, max_requests=None):
    _inputs(events, source_catalog)
    _require(type(max_events_per_request) is int and max_events_per_request > 0, "Invalid event batch bound")
    _require(max_requests is None or type(max_requests) is int and max_requests > 0, "Invalid request bound")
    batches = [events[i:i + max_events_per_request] for i in range(0, len(events), max_events_per_request)]
    chosen = batches if max_requests is None else batches[:max_requests]
    requests = [formalization_request(batch, source_catalog, request_id=f"compiler-grounded:{i:04d}")
                for i, batch in enumerate(chosen)]
    selected = [e["id"] for batch in chosen for e in batch]
    return requests, {"total_events": len(events), "selected_events": len(selected),
                      "complete_event_coverage": len(selected) == len(events),
                      "unselected_event_ids": [e["id"] for e in events if e["id"] not in selected],
                      "max_events_per_request": max_events_per_request, "max_requests": max_requests,
                      "asserted_order_scope": "within_request_only",
                      "covered_directed_event_pairs": sum(len(batch) * (len(batch) - 1) for batch in chosen),
                      "total_directed_event_pairs": len(events) * (len(events) - 1),
                      "date_comparison_scope": "all_combined_verified_events"}


def _request_inputs(request):
    _inputs(request["events"], request["source_catalog"])
    _require(request["input_sha256"] == reasoner._digest({"events": request["events"],
                                                          "source_catalog": request["source_catalog"]}),
             "Compiler input fingerprint changed")


def schema_for(request):
    evidence = _array(_enum(e["id"] for e in request["source_catalog"]), unique=True)
    if request["kind"] == VERIFY_PROTOCOL:
        return _obj({atom["id"]: _obj({"decision": _enum(DECISIONS), "evidence_ids": evidence,
                                        "reason": _text()}) for atom in request["atoms"]})
    _require(request["kind"] == PROTOCOL, "Unknown grounded compiler protocol")
    semantic = {"polarity": _enum(("positive", "negative", "unknown")),
                "assertion": _enum(("asserted", "reported", "conditional", "hypothetical", "unknown")),
                "modality": _enum(("actual", "possible", "necessary", "intended", "unknown"))}
    timing = _obj({"status": _enum(("known", "unknown", "ambiguous")),
                   "earliest_start": {"type": "string"}, "latest_end": {"type": "string"},
                   "precision": _enum(("day", "month", "year", "range", "unknown")),
                   "date_role": _enum(("event_time", "named_reference", "other", "unknown")),
                   "evidence_ids": evidence})
    subevent = _obj({"local_id": _text(), "text": _text(), "evidence_ids": evidence,
                     **semantic, "time": timing})
    endpoint = _obj({"event_id": _enum(e["id"] for e in request["events"]), "local_id": _text()})
    order = _obj({"local_id": _text(), "kind": _enum(("before", "after")), "head": endpoint,
                  "tail": endpoint, "evidence_ids": evidence, **semantic})
    entry = _obj({"status": _enum(("formalized", "unformalized")),
                  "subevents": _array(subevent), "reason": {"type": "string"}})
    return _obj({"events": _obj({e["id"]: entry for e in request["events"]}), "orders": _array(order)})


def _validate(value, schema):
    try:
        jsonschema.Draft202012Validator(schema).validate(value)
    except jsonschema.ValidationError as exc:
        raise ValueError("Invalid grounded compiler response at " + "/".join(map(str, exc.absolute_path))
                         + ": " + exc.message) from exc


def _time(timing):
    low, high, precision = timing["earliest_start"], timing["latest_end"], timing["precision"]
    if timing["status"] != "known":
        _require(low == high == "" and precision == "unknown", "Unknown/ambiguous dates cannot carry guessed bounds")
        return
    try:
        start, end = date.fromisoformat(low), date.fromisoformat(high)
    except (TypeError, ValueError) as exc:
        raise ValueError("Invalid ISO date bounds") from exc
    _require(start.isoformat() == low and end.isoformat() == high and start <= end, "Noncanonical or inverted ISO bounds")
    _require(precision != "unknown", "Known date requires precision")
    if precision == "day":
        _require(start == end, "Day precision needs identical bounds")
    elif precision == "month":
        _require((start.year, start.month) == (end.year, end.month) and start.day == 1
                 and end.day == monthrange(end.year, end.month)[1], "Month precision must cover the whole month")
    elif precision == "year":
        _require(start.year == end.year and (start.month, start.day) == (1, 1)
                 and (end.month, end.day) == (12, 31), "Year precision must cover the whole year")


def classify(request, raw):
    value = parse_json(raw)
    _validate(value, schema_for(request))
    if request["kind"] == VERIFY_PROTOCOL:
        for decision in value.values():
            _require(decision["reason"].strip(), "Verifier reason cannot be blank")
            _require(decision["decision"] != "supported" or decision["evidence_ids"], "Supported needs direct source evidence")
        return value
    _request_inputs(request)
    known = set()
    for parent, entry in value["events"].items():
        _require((entry["status"] == "formalized") == bool(entry["subevents"]), "Formalization status and subevents disagree")
        for subevent in entry["subevents"]:
            _require(subevent["local_id"].strip() and subevent["text"].strip(), "Empty subevent identifier/text")
            key = parent, subevent["local_id"]
            _require(key not in known, "Duplicate subevent ID")
            known.add(key)
            _time(subevent["time"])
    order_ids = set()
    for order in value["orders"]:
        _require(order["local_id"].strip() and order["local_id"] not in order_ids, "Duplicate or empty order ID")
        order_ids.add(order["local_id"])
        for endpoint in (order["head"], order["tail"]):
            _require((endpoint["event_id"], endpoint["local_id"]) in known, "Order references missing subevent")
    return value


def _binding_body(request, parsed):
    catalog = {e["id"]: e for e in request["source_catalog"]}
    proposed, findings, endpoints = [], {}, {}
    source_digest = reasoner._digest(request["source_catalog"])
    for parent, entry in parsed["events"].items():
        texts = [s["text"] for s in entry["subevents"]]
        for subevent in entry["subevents"]:
            evidence = sorted(set(subevent["evidence_ids"] + subevent["time"]["evidence_ids"]))
            event_id = "subevent:" + reasoner._digest({"source": source_digest, "parent": parent,
                                                       "local_id": subevent["local_id"], "text": subevent["text"]})
            atom = {"kind": "event", "parent_event_id": parent, "event_id": event_id,
                    **deepcopy(subevent), "evidence_ids": evidence,
                    "source_bindings": [deepcopy(catalog[e]) for e in evidence]}
            atom["id"] = "proposal:" + reasoner._digest(atom)
            endpoints[parent, subevent["local_id"]] = atom
            proposed.append(atom)
            issues = []
            if not subevent["evidence_ids"]:
                issues.append("missing_event_source_evidence")
            if subevent["time"]["status"] == "known" and not subevent["time"]["evidence_ids"]:
                issues.append("missing_time_source_evidence")
            if texts.count(subevent["text"]) > 1:
                issues.append("duplicate_subevent_text_cannot_split_one_activity")
            if issues:
                findings[atom["id"]] = issues
    for order in parsed["orders"]:
        first, second = (endpoints[x["event_id"], x["local_id"]] for x in (order["head"], order["tail"]))
        atom = {**deepcopy(order), "head": first["event_id"], "tail": second["event_id"],
                "endpoint_proposal_ids": [first["id"], second["id"]],
                "parent_event_ids": [first["parent_event_id"], second["parent_event_id"]],
                "source_bindings": [deepcopy(catalog[e]) for e in order["evidence_ids"]]}
        atom["id"] = "proposal:" + reasoner._digest(atom)
        proposed.append(atom)
        issues = []
        if not order["evidence_ids"]:
            issues.append("missing_order_source_evidence")
        if first["id"] in findings or second["id"] in findings:
            issues.append("unbound_order_endpoint")
        if issues:
            findings[atom["id"]] = issues
    _require(len({p["id"] for p in proposed}) == len(proposed), "Duplicate proposed atom")
    return {"protocol": PROTOCOL, "source_catalog": deepcopy(request["source_catalog"]),
            "proposed_primitives": proposed, "bound_primitives": [p for p in proposed if p["id"] not in findings],
            "binding_findings": findings, "semantic_source_fidelity": "not_established_by_binding"}


def bind_proposals(request, parsed):
    _require(request["kind"] == PROTOCOL, "Expected formalization request")
    parsed = classify(request, _dump(parsed))
    return {**_binding_body(request, parsed), "requests": [deepcopy(request)], "responses": [deepcopy(parsed)]}


def _checked_bound(bound):
    _require(isinstance(bound, dict) and len(bound["requests"]) == len(bound["responses"])
             and bound["requests"], "Missing binding provenance")
    expected = combine_bindings([bind_proposals(q, p) for q, p in zip(bound["requests"], bound["responses"])],
                                _checked=True)
    _require(_dump(expected) == _dump(bound), "Bound compiler projection changed")
    return bound


def combine_bindings(reports, *, _checked=False):
    _require(isinstance(reports, list) and reports, "No binding reports")
    if not _checked:
        for report in reports:
            _checked_bound(report)
    catalog = reports[0]["source_catalog"]
    _require(all(_dump(report["source_catalog"]) == _dump(catalog) for report in reports), "Evidence catalog differs across batches")
    result = {key: deepcopy(reports[0][key]) for key in ("protocol", "source_catalog", "semantic_source_fidelity")}
    for key in ("requests", "responses", "proposed_primitives", "bound_primitives"):
        result[key] = [deepcopy(value) for report in reports for value in report[key]]
    ids = [p["id"] for p in result["proposed_primitives"]]
    parents = [e["id"] for q in result["requests"] for e in q["events"]]
    _require(len(ids) == len(set(ids)) and len(parents) == len(set(parents)), "Duplicate atom or parent event across batches")
    result["binding_findings"] = {k: deepcopy(v) for report in reports for k, v in report["binding_findings"].items()}
    return result


def verifier_request(bound, *, request_id="compiler-grounded:verify"):
    _checked_bound(bound)
    atoms = deepcopy(bound["bound_primitives"])
    prompt = (
        "Independently verify each proposed atom against the FULL ORIGINAL SOURCE_CATALOG. "
        "Do not trust native extraction, compiler reasoning or an evidence ID merely because it exists. "
        "Check that each atomic subevent really is separately asserted and preserves its participants, "
        "polarity, modality, date role, granularity and entire interval. Check ISO bounds against the "
        "source's language and ambiguity. A named year is not automatically an event date. Check "
        "before/after direction and both referenced event meanings, not just endpoint existence. "
        "Use supported only when ALL content of the atom is supported. Use contradicted for "
        "source conflict, otherwise insufficient. Missing or ambiguous evidence is insufficient. "
        "Do not repair, normalize, invent or replace the atom. Cite original evidence IDs and give "
        "a reason. Source fidelity is a separate assessment from formal proof validity. "
        "Return exactly one decision for EVERY required proposal ID, JSON only.\n"
        "SOURCE_CATALOG:\n" + _dump(bound["source_catalog"]) + "\nPROPOSED_ATOMS:\n" + _dump(atoms))
    return {"request_id": request_id, "kind": VERIFY_PROTOCOL, "protocol": VERIFY_PROTOCOL,
            "item_ids": [p["id"] for p in atoms], "atoms": atoms,
            "source_catalog": deepcopy(bound["source_catalog"]), "bound_sha256": reasoner._digest(bound),
            "parameters": {"max_new_tokens": 4096}, "prompt": prompt,
            "messages": [{"role": "user", "content": prompt}]}


def _actual(atom):
    return atom["polarity"] == "positive" and atom["assertion"] == "asserted" and atom["modality"] == "actual"


def solve(bound, decisions=None, *, conflict_policy=LOCAL_POLICY):
    _checked_bound(bound)
    _require(conflict_policy in (LOCAL_POLICY, WHOLE_POLICY), "Unknown exclusion policy")
    verification = verifier_request(bound)
    if decisions is None:
        supported = []
    else:
        decisions = classify(verification, _dump(decisions))
        supported = [p for p in bound["bound_primitives"] if decisions[p["id"]]["decision"] == "supported"]
    supported_ids = {p["id"] for p in supported}
    actual_events = {p["id"] for p in supported if p["kind"] == "event" and _actual(p)}
    primitives, exclusions = [], {}
    for atom in bound["bound_primitives"]:
        if atom["id"] not in supported_ids:
            exclusions[atom["id"]] = "not_verifier_supported"
            continue
        if not _actual(atom):
            exclusions[atom["id"]] = "nonpositive_nonasserted_or_modal"
            continue
        primitive = {"id": atom["id"], "source_item_ids": sorted(set(atom["evidence_ids"] + decisions[atom["id"]]["evidence_ids"])),
                     "input_spans": deepcopy(atom["source_bindings"]),
                     "grounded_compiler_proposal": deepcopy(atom),
                     "source_verifier_decision": deepcopy(decisions[atom["id"]])}
        if atom["kind"] == "event":
            timing = atom["time"]
            if timing["status"] != "known" or timing["date_role"] != "event_time":
                exclusions[atom["id"]] = "no_supported_event_time"
                continue
            primitive.update(kind="event_time", event_id=atom["event_id"],
                             earliest_start=timing["earliest_start"], latest_end=timing["latest_end"])
        else:
            if not set(atom["endpoint_proposal_ids"]) <= actual_events:
                exclusions[atom["id"]] = "unsupported_or_nonactual_order_endpoint"
                continue
            primitive.update(kind=atom["kind"], head=atom["head"], tail=atom["tail"])
            # Bind endpoint meanings and verifier judgments into order terminals
            # as well, so a proof cannot silently change its event dependencies.
            primitive["endpoint_support"] = [deepcopy(p) for p in supported if p["id"] in atom["endpoint_proposal_ids"]]
            primitive["endpoint_decisions"] = {ident: deepcopy(decisions[ident]) for ident in atom["endpoint_proposal_ids"]}
            primitive["source_item_ids"] = sorted(set(primitive["source_item_ids"]).union(
                *(set(p["evidence_ids"]) | set(decisions[p["id"]]["evidence_ids"]) for p in primitive["endpoint_support"])))
        primitives.append(primitive)
    if conflict_policy == LOCAL_POLICY:
        report = conflict.diagnose(primitives)
        eligible, result = report["eligible_primitives"], report["alternative"]
        policy_details = {key: report[key] for key in ("excluded_primitive_ids", "excluded_asserted_components",
                                                       "incompatible_time_nodes", "cyclic_asserted_orders", "original")}
    else:
        result = {k: v for k, v in reasoner.materialize(primitives).items() if k != "elapsed_seconds"}
        eligible, policy_details = primitives, {"excluded_components": result["excluded_components"]}
    proofs = {p["id"]: reasoner.verify_proof(p, eligible, result["derived"]) for p in result["derived"]}
    _require(all(proofs.values()), "Unchanged proof verifier rejected a conclusion")
    return {"protocol": PROTOCOL, "conflict_policy": conflict_policy,
            "proposed_primitives": deepcopy(bound["proposed_primitives"]),
            "bound_primitives": deepcopy(bound["bound_primitives"]),
            "verifier_supported_primitives": deepcopy(supported), "verifier_decisions": deepcopy(decisions),
            "solver_primitives": primitives, "eligible_primitives": eligible,
            "solver_exclusions": exclusions, "policy_details": policy_details,
            "derived": result["derived"], "proofs": proofs, "residual_conflicts": result["conflicts"],
            "bound_sha256": reasoner._digest(bound), "eligible_sha256": reasoner._digest(eligible),
            "proof_scope": "eligible_primitives_under_selected_policy",
            "source_fidelity": "verifier_assessment_not_independent_gold_truth", "quality_gain_claimed": False}


def inspect_response(request, raw_response):
    """Capture parse feedback without losing the original proposal bytes."""
    try:
        parsed = classify(request, raw_response)
        return {"request_sha256": reasoner._digest(request), "raw_response": raw_response,
                "status": "valid", "parsed": parsed, "errors": []}
    except (ValueError, TypeError, KeyError) as exc:
        return {"request_sha256": reasoner._digest(request), "raw_response": raw_response,
                "status": "invalid", "parsed": None,
                "errors": [{"stage": "parse", "code": type(exc).__name__, "message": str(exc)}]}


def execution_feedback(result):
    """Report logical execution conflicts, never verifier disagreement as syntax."""
    old = result["policy_details"].get("original", result)
    conflicts = old.get("conflicts", old.get("residual_conflicts", []))
    return [{"stage": "execution", "code": issue["kind"], "message": _dump(issue)} for issue in conflicts]


def repair_request(request, raw_response, errors, *, attempt=1, max_repairs=1, enabled=False):
    """Explicit alternative branch. The caller saves/dispatches each new attempt.

    This is feedback-guided resampling, not lossless syntax repair. Revised
    meanings require fresh binding and source verification before any reasoning.
    """
    _require(enabled is True, "Feedback repair is disabled by default")
    _require(request["kind"] == PROTOCOL, "Only formalization has this repair branch")
    _request_inputs(request)
    _require(type(max_repairs) is int and 0 <= max_repairs <= MAX_REPAIRS, "Invalid repair cap")
    previous = request.get("repair", {})
    _require(type(attempt) is int and 1 <= attempt <= max_repairs
             and attempt == previous.get("attempt", 0) + 1, "Repair attempt is out of sequence or over cap")
    _require(not previous or previous["max_repairs"] == max_repairs, "Cannot change cap inside repair branch")
    _require(isinstance(raw_response, str) and isinstance(errors, list) and errors, "Missing original response or feedback")
    for error in errors:
        _require(isinstance(error, dict) and set(error) == {"stage", "code", "message"}
                 and error["stage"] in ("parse", "execution")
                 and all(isinstance(error[key], str) and error[key].strip() for key in error),
                 "Only explicit parse/execution errors may guide this branch")
    repaired = deepcopy(request)
    root_id = previous.get("original_request_id", request["request_id"])
    repaired["request_id"] = root_id + f":feedback:{attempt}"
    repaired["repair"] = {"attempt": attempt, "max_repairs": max_repairs,
                           "original_request_id": root_id,
                           "original_request_sha256": previous.get("original_request_sha256", reasoner._digest(request)),
                           "original_raw_response": previous.get("original_raw_response", raw_response),
                           "previous_request_sha256": reasoner._digest(request),
                           "previous_raw_response": raw_response, "errors": deepcopy(errors),
                           "semantic_preservation_guaranteed": False, "requires_fresh_source_verification": True}
    feedback = ("Separate feedback-guided formalization attempt. Address only the reported parse/execution "
                "errors while preserving the original source meaning. Do not invent dates, delete true "
                "assertions or split one event just to satisfy the solver. If source meaning is uncertain "
                "use unformalized/unknown/ambiguous instead. A changed proposal needs new independent "
                "source verification. Return the complete original JSON contract, not a patch.\nERRORS:\n" + _dump(errors))
    repaired["messages"] += [{"role": "assistant", "content": raw_response}, {"role": "user", "content": feedback}]
    repaired["prompt"] = feedback
    return repaired
