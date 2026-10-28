"""Pure, reversible EE/VV source guard; no inference or transport management.

Exact source binding is not proof of semantic entailment. Facets and removal
permissions are fallible external judgments. Historical conditions are unchanged.
"""
from copy import deepcopy
from hashlib import sha256

from jsonschema import Draft202012Validator, ValidationError

from Experiments.fair_comparison_oct23_v1 import scope_prefix
from Experiments.strict_autoschemakg import grounded_evidence_v1 as evidence
from Tools.experiments.independent_repair_transfer_oct23_v1 import controller


PROTOCOL = "whole-relation-source-guard-oct24-v1"
FACETS = ("head", "tail", "relation_and_direction", "qualifications")
STATUSES = controller.STATUSES
SYSTEM = controller.CHECK_SYSTEM + "\n\n" + """EE/VV FACET CONTRACT:
Judge only the eligible EE/VV IDs. The full inventory is context, not evidence.
Keep each original value intact. EV records are context only and cannot be removed.
head: Check the complete Head assertion/description and its identity and roles.
tail: Check the complete Tail assertion/description and its identity and roles.
For EE these can be entities; do not demand two events, chronology or causality.
relation_and_direction: Check the ENTIRE Head + Relation + Tail assertion, its
actual relation and its direction together. Correct endpoints alone do not
establish their link. Do not infer causality from mention order or cooccurrence.
qualifications: Check necessary polarity, time, modality, attribution, quantities
and conditions. Optional extra detail or a preferred paraphrase is not a defect.
For each facet give reason, status and exact contiguous original-source quotes.
Supported establishes the whole facet; contradicted requires positive conflict;
unsupported requires an unambiguous interpreted claim without source warrant;
undetermined preserves unsettled interpretation. Decisive facets need quotes;
undetermined facets may have empty evidence. A quote is not itself entailment.
Return every eligible ID once. Do not supply an overall status or repair values.
remove_authorized and preserves_supported_content separately judge whether
removal is necessary and preserves ALL supported content in the remaining full
inventory. Never authorize removal of a supported or unsettled original.
VV ONLY, existing native relation convention:
""" + scope_prefix.CLAUSES["relation"]


def _require(value, message):
    if not value:
        raise ValueError(message)


def _context(source, inventory, eligible_ids):
    # Reuse the complete native contract; unknown/extra fields are never dropped.
    controller.make_check(source, inventory, [], eligible_ids=[])
    catalog = evidence.catalog(source)
    evidence.validate_catalog(catalog, source)
    allowed = [row["id"] for row in inventory if row["category"] in {"EE", "VV"}]
    selected = allowed if eligible_ids is None else eligible_ids
    _require(type(selected) is list and all(type(x) is str for x in selected)
             and len(selected) == len(set(selected)) and set(selected) <= set(allowed),
             "Eligible IDs must be unique existing EE/VV IDs")
    return deepcopy(selected), catalog


def build_request(source, inventory, eligible_ids=None):
    """Build a packet accepted by the existing runner._invoke interface."""
    selected, catalog = _context(source, inventory, eligible_ids)
    base = controller.make_check(source, inventory, [], eligible_ids=selected)
    facet = controller._obj({"reason": deepcopy(controller.TEXT),
        "status": {"enum": list(STATUSES)}, "evidence_quotes": deepcopy(controller.QUOTES)})
    row = controller._obj({"id": {"enum": selected} if selected else {"type": "string"},
        "facets": controller._obj({name: deepcopy(facet) for name in FACETS}),
        "remove_authorized": {"type": "boolean"},
        "preserves_supported_content": {"type": "boolean"}})
    rows = controller._array(row)
    rows.update(minItems=len(selected), maxItems=len(selected))
    # Full source appears once; paragraph IDs/offsets are a lossless lookup aid.
    payload = {"source": source, "inventory": deepcopy(inventory),
        "eligible_original_ids": selected,
        "source_catalog": [{k: item[k] for k in ("id", "start", "end")} for item in catalog]}
    packet = controller._request(SYSTEM, payload, controller._obj({"originals": rows}))
    packet["protocol"] = PROTOCOL
    # The original controller remains the application contract, not a new gate.
    _require(base["schema"]["properties"]["originals"]["minItems"] == len(selected),
             "Original application roster differs")
    return packet


def validate_response(source, inventory, parsed, eligible_ids=None):
    """Return controller judgments; never infer truth from exact quote matches."""
    selected, _ = _context(source, inventory, eligible_ids)
    Draft202012Validator(build_request(source, inventory, selected)["schema"]).validate(parsed)
    rows = parsed["originals"]
    ids = [row["id"] for row in rows]
    _require(len(ids) == len(set(ids)) and set(ids) == set(selected),
             "Missing, duplicate or foreign guard response IDs")
    judgments = []
    for row in rows:
        facets = row["facets"]
        for value in facets.values():
            _require(bool(value["reason"].strip()), "Nonempty facet reason required")
            controller._quotes(source, value["evidence_quotes"],
                               decisive=value["status"] != "undetermined")
        statuses = [facets[name]["status"] for name in FACETS]
        status = ("supported" if all(x == "supported" for x in statuses) else
                  "contradicted" if "contradicted" in statuses else
                  "unsupported" if "unsupported" in statuses else "undetermined")
        defect = ("source_conflict" if status == "contradicted" else
                  "necessary_qualification_loss" if status == "unsupported" and
                  facets["qualifications"]["status"] == "unsupported" else
                  "unlicensed_assertion" if status == "unsupported" else "none")
        quotes = [quote for name in FACETS for quote in facets[name]["evidence_quotes"]]
        judgments.append({"id": row["id"], "status": status,
            "reason": " | ".join(name + "=" + facets[name]["status"] + ": " +
                                  facets[name]["reason"] for name in FACETS),
            "evidence_quotes": quotes, "defect_kind": defect,
            "remove_authorized": row["remove_authorized"],
            "preserves_supported_content": row["preserves_supported_content"]})
    return {"originals": judgments, "proposals": []}


def apply_response(source, inventory, parsed=None, *, technical_failure=False, eligible_ids=None):
    """Apply only authorized removals; invalid/unknown results preserve originals."""
    _require(type(technical_failure) is bool, "Explicit technical failure boolean required")
    selected, _ = _context(source, inventory, eligible_ids)
    judgments, error = None, None
    if not technical_failure:
        try:
            if not selected and parsed is None:
                parsed = {"originals": []}
            judgments = validate_response(source, inventory, parsed, selected)
        except (ValueError, TypeError, KeyError, ValidationError) as exc:
            technical_failure, error = True, type(exc).__name__
    if technical_failure:
        # Use the unchanged controller with explicit unsettled rows, never
        # transform missing evidence or technical failure into negative truth.
        judgments = {"originals": [{"id": ident, "status": "undetermined",
            "reason": "Guard technical failure; original retained.", "evidence_quotes": [],
            "remove_authorized": False, "preserves_supported_content": False,
            "defect_kind": "none"} for ident in selected], "proposals": []}
    result = controller.apply_checked(source, inventory, [], judgments, eligible_ids=selected)
    remaining = {row["id"]: i for i, row in enumerate(result["inventory"])}
    by_id = {row["id"]: row for row in judgments["originals"]}
    ledger = [{"ordinal": i, "record": deepcopy(row),
        "after_ordinal": remaining.get(row["id"]),
        "action": "retained" if row["id"] in remaining else "removed",
        "judgment": deepcopy(by_id.get(row["id"]))} for i, row in enumerate(inventory)]
    result.update(protocol=PROTOCOL, complete=not technical_failure,
        technical_failure=technical_failure, error_class=error,
        eligible_ids=selected, source_sha256=sha256(source.encode("utf8")).hexdigest(),
        parsed_response=deepcopy(parsed), controller_judgments=deepcopy(judgments),
        ledger=ledger, ledger_sha256=controller._digest(ledger),
        binding_is_not_semantic_entailment=True)
    return result


def restore(result):
    """Verify the complete reversible ledger and return a fresh original copy."""
    _require(type(result) is dict and result.get("protocol") == PROTOCOL,
             "Exact guard result required")
    ledger = result["ledger"]
    _require(type(ledger) is list and controller._digest(ledger) == result["ledger_sha256"],
             "Guard ledger changed")
    original, after = [], []
    for i, entry in enumerate(ledger):
        _require(type(entry["ordinal"]) is int and entry["ordinal"] == i
                 and entry["action"] in {"retained", "removed"}, "Invalid ledger order/action")
        original.append(deepcopy(entry["record"]))
        expected = len(after) if entry["action"] == "retained" else None
        _require(entry["after_ordinal"] is None if expected is None else
                 type(entry["after_ordinal"]) is int and entry["after_ordinal"] == expected,
                 "Invalid ledger result position")
        if expected is not None:
            after.append(deepcopy(entry["record"]))
    _require(controller._digest(original) == result["before_sha256"]
             and controller._digest(after) == result["after_sha256"]
             and controller._digest(result["inventory"]) == result["after_sha256"]
             and result["added_ids"] == []
             and sorted(row["record"]["id"] for row in ledger if row["action"] == "removed")
                 == result["removed_ids"], "Guard original/result hash or removal roster differs")
    return original
