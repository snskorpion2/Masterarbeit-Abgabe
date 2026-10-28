"""Small C1 entry point over the unchanged whole-statement guard.

``make_guard(completion)`` binds a callable that accepts the existing request
packet and returns parsed JSON. All groups see the original full context.
Only after every group validates is the unchanged application run once.
No credentials, provider imports or calls are made at module import.
"""
from copy import deepcopy
from hashlib import sha256

from . import guard as original

FACET_POLICY = "whole-relation-facet-deterministic-delete-c1-oct24-v1"


class GuardTechnicalFailure(RuntimeError):
    """No removal was applied; ``kept`` is the complete untouched input copy."""

    def __init__(self, inventory, cause):
        super().__init__("Whole-statement guard failed; every original is retained.")
        self.kept = deepcopy(inventory)
        self.removed_with_reason = []
        self.error_class = type(cause).__name__


def make_guard(completion, *, max_statements=1):
    """Return ``guard(inventory, source_text) -> (kept, removed_with_reason)``.

    ``completion(packet)`` must either return the complete parsed response or
    raise an exception. It owns provider/model qualification and call receipts.
    The default one-statement groups reduce output length without shortening
    the source or inventory context. They do not cause repeated application.
    """
    if not callable(completion):
        raise TypeError("A completion callable is required")
    if type(max_statements) is not int or max_statements <= 0:
        raise ValueError("max_statements must be a positive integer")

    def bound_guard(inventory, source_text):
        before = deepcopy(inventory)
        try:
            # This validates the complete original native contract, including
            # duplicate IDs and unknown fields, without dropping any values.
            original.build_request(source_text, before)
            selected = [row["id"] for row in before if row["category"] in {"EE", "VV"}]
            if not selected:
                return deepcopy(before), []
            rows = []
            for offset in range(0, len(selected), max_statements):
                group = selected[offset:offset + max_statements]
                packet = original.build_request(source_text, before, eligible_ids=group)
                parsed = completion(deepcopy(packet))
                original.validate_response(source_text, before, parsed, eligible_ids=group)
                rows.extend(deepcopy(parsed["originals"]))
            combined = {"originals": rows}
            original.validate_response(source_text, before, combined, eligible_ids=selected)
            result = original.apply_response(source_text, before, combined, eligible_ids=selected)
            if not result["complete"] or original.restore(result) != before:
                raise ValueError("Whole-statement application or reversible ledger failed")
            facets = {row["id"]: deepcopy(row["facets"]) for row in combined["originals"]}
            removed = []
            for entry in result["ledger"]:
                if entry["action"] != "removed":
                    continue
                judgment = entry["judgment"]
                removed.append({
                    "ordinal": entry["ordinal"],
                    "record": deepcopy(entry["record"]),
                    "reason": judgment["reason"],
                    "status": judgment["status"],
                    "defect_kind": judgment["defect_kind"],
                    "evidence_quotes": deepcopy(judgment["evidence_quotes"]),
                    "facets": facets[entry["record"]["id"]],
                    "remove_authorized": judgment["remove_authorized"],
                    "preserves_supported_content": judgment["preserves_supported_content"],
                })
            return deepcopy(result["inventory"]), removed
        except Exception as cause:
            raise GuardTechnicalFailure(before, cause) from cause

    return bound_guard


def guard(inventory, source_text):
    """Use the separately qualified Mantle condition with the two-argument API.

    Backend creation is lazy. A missing qualification or provider failure raises
    ``GuardTechnicalFailure`` and exposes every untouched original in ``kept``.
    For CPU use, bind ``make_guard(fake_completion)`` instead.
    """
    completion = None

    def lazy_completion(packet):
        nonlocal completion
        if completion is None:
            from .mantle_condition_v1 import default_completion
            completion = default_completion()
        return completion(packet)

    return make_guard(lazy_completion)(inventory, source_text)


def apply_facet_response(source, inventory, parsed, eligible_ids=None, *, legacy=False):
    """A3c: remove iff a bound negative facet has valid original-source quotes.

    Model permission/preservation fields never decide this operation. A valid
    negative trigger survives unrelated quote faults. A quote-invalid keep is
    retained but remains unassessed; it is not a positive qualification success.
    The historical make_guard/default admission above remain separate.
    """
    from . import a3c_core as core
    before = deepcopy(inventory)
    selected, _ = original._context(source, before, eligible_ids)
    assessment, error = None, None
    try:
        assessment = core.assess_response(source, before, parsed, selected, legacy=legacy)
    except (ValueError, TypeError, KeyError, original.ValidationError) as cause:
        error = type(cause).__name__
    decisions = []
    if assessment is None:
        decisions = [{"id": ident, "removed": False, "assessed": False,
            "trigger_facets": [], "quote_errors": [], "status": "undetermined"} for ident in selected]
    else:
        for row in assessment["originals"]:
            triggers = [name for name in core.FACETS
                if row["facets"][name]["status"] in {"unsupported", "contradicted"}
                and row["facets"][name]["quote_valid"]]
            quote_errors = [{"facet": name, "errors": row["facets"][name]["quote_errors"]}
                for name in core.FACETS if not row["facets"][name]["quote_valid"]]
            statuses = [row["facets"][name]["status"] for name in core.FACETS]
            decisions.append({"id": row["id"], "removed": bool(triggers),
                "assessed": bool(triggers) or not quote_errors, "trigger_facets": triggers,
                "quote_errors": quote_errors, "facet_statuses": dict(zip(core.FACETS, statuses)),
                "status": "contradicted" if any(row["facets"][f]["status"] == "contradicted" for f in triggers)
                    else "unsupported" if triggers else "supported"
                    if all(s == "supported" for s in statuses) and not quote_errors else "undetermined"})
    by_id = {row["id"]: row for row in decisions}
    removed = {row["id"] for row in decisions if row["removed"]}
    after = [deepcopy(row) for row in before if row["id"] not in removed]
    positions = {row["id"]: i for i, row in enumerate(after)}
    ledger = [{"ordinal": i, "record": deepcopy(row), "after_ordinal": positions.get(row["id"]),
        "action": "removed" if row["id"] in removed else "retained",
        "judgment": deepcopy(by_id.get(row["id"]))} for i, row in enumerate(before)]
    return {"protocol": FACET_POLICY, "inventory": after,
        "removed_ids": [row["id"] for row in before if row["id"] in removed], "added_ids": [],
        "complete": assessment is not None and all(row["assessed"] for row in decisions),
        "structure_valid": assessment is not None, "error_class": error,
        "row_decisions": decisions, "assessment": assessment,
        "eligible_ids": selected, "legacy_mappings": assessment["legacy_mappings"] if assessment else [],
        "source_sha256": sha256(source.encode("utf8")).hexdigest(),
        "before_sha256": original.controller._digest(before),
        "after_sha256": original.controller._digest(after),
        "ledger": ledger, "ledger_sha256": original.controller._digest(ledger),
        "binding_is_not_semantic_entailment": True}


def restore_facet_result(result):
    """Verify the A3c reversible ledger, including unchanged original values."""
    original._require(result.get("protocol") == FACET_POLICY, "Wrong facet result protocol")
    ledger = result["ledger"]
    original._require(original.controller._digest(ledger) == result["ledger_sha256"], "Changed facet ledger")
    before, after = [], []
    for i, entry in enumerate(ledger):
        original._require(type(entry["ordinal"]) is int and entry["ordinal"] == i
            and entry["action"] in {"retained", "removed"}, "Invalid facet ledger order/action")
        before.append(deepcopy(entry["record"]))
        if entry["action"] == "retained":
            original._require(type(entry["after_ordinal"]) is int and entry["after_ordinal"] == len(after),
                              "Changed facet result position")
            after.append(deepcopy(entry["record"]))
        else:
            original._require(entry["after_ordinal"] is None, "Removed facet record has a result position")
    original._require(original.controller._digest(before) == result["before_sha256"]
        and original.controller._digest(after) == result["after_sha256"]
        and after == result["inventory"] and result["added_ids"] == []
        and [row["record"]["id"] for row in ledger if row["action"] == "removed"] == result["removed_ids"],
        "Facet ledger original/result or removed IDs changed")
    return before


def make_facet_guard(completion, *, max_statements=10):
    """Explicit A3c factory; production selection requires its own admission."""
    from . import a3c_core as core
    if not callable(completion) or type(max_statements) is not int or not 1 <= max_statements <= 10:
        raise ValueError("Callable completion and group size one to ten required")
    def bound(inventory, source_text):
        before = deepcopy(inventory)
        try:
            selected, _ = original._context(source_text, before, None)
            rows = []
            for offset in range(0, len(selected), max_statements):
                group = selected[offset:offset + max_statements]
                packet = core.build_request(source_text, before, group)
                parsed = completion(deepcopy(packet))
                core.assess_response(source_text, before, parsed, group)
                rows.extend(deepcopy(parsed["originals"]))
            result = apply_facet_response(source_text, before, {"originals": rows}, selected)
            if not result["structure_valid"] or restore_facet_result(result) != before:
                raise ValueError("Invalid complete facet roster or reversible ledger")
            parsed_rows = {row["id"]: row for row in result["assessment"]["originals"]}
            removed = []
            for entry in result["ledger"]:
                if entry["action"] != "removed":
                    continue
                verdict = entry["judgment"]
                facets = parsed_rows[entry["record"]["id"]]["projected_facets"]
                removed.append({"ordinal": entry["ordinal"], "record": deepcopy(entry["record"]),
                    "reason": " | ".join(name + ": " + facets[name]["reason"] for name in verdict["trigger_facets"]),
                    "status": verdict["status"], "trigger_facets": verdict["trigger_facets"],
                    "evidence_quotes": [q for name in verdict["trigger_facets"] for q in facets[name]["evidence_quotes"]],
                    "facets": deepcopy(facets), "other_quote_errors": deepcopy(verdict["quote_errors"]),
                    "decision_policy": FACET_POLICY})
            return deepcopy(result["inventory"]), removed
        except Exception as cause:
            raise GuardTechnicalFailure(before, cause) from cause
    return bound
