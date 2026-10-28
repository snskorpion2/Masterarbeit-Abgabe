"""Pure facet request/inspection for A3c; no application or admission decision.

Exact source binding is not proof of semantic entailment. Quote validity below
is mechanical and never changes a supplied facet status or establishes truth.
"""
from copy import deepcopy
from hashlib import sha256

from jsonschema import Draft202012Validator

from Tools.experiments.whole_relation_guard_oct24_v1 import guard


PROTOCOL = "whole-relation-facet-only-a3c-oct24-v1"
FACETS = guard.FACETS
STATUSES = guard.STATUSES
controller = guard.controller
LEGACY_DECISION_KEYS = ("remove_authorized", "preserves_supported_content")
LEGACY_ALIAS = "preserves_supported_content_content"


def _replace_once(text, old, new):
    guard._require(text.count(old) == 1, "Pinned guard prompt section differs")
    return text.replace(old, new, 1)


def _system():
    text = _replace_once(guard.SYSTEM, """For each eligible original explicitly judge removal necessity,
defect kind and whether removing it (with accepted proposals and remaining inventory) preserves
ALL supported content. Removal is never justified by absent optional detail, an additional
co-participant, a preferred paraphrase or an unverified schema expectation. A qualification loss
must be necessary to the truth/scope of the assertion. Supported or undetermined originals
must not be authorized for removal. """, """Absent optional detail, an additional co-participant,
a preferred paraphrase or an unverified schema expectation is not a defect. A qualification
loss must be necessary to the truth/scope of the assertion. """)
    text = _replace_once(text,
        "Keep each original value intact. EV records are context only and cannot be removed.",
        "Assess the full original values. EV records are context only, without facet judgments.")
    text = _replace_once(text, """remove_authorized and preserves_supported_content separately judge whether
removal is necessary and preserves ALL supported content in the remaining full
inventory. Never authorize removal of a supported or unsettled original.
""", "")
    return text + "\nReturn only the declared originals [{id, facets}] JSON, with the four facet judgments. " \
        "Give no overall status, permission, preservation or application decision."


SYSTEM = _system()


def _schema(selected, *, inspection=False):
    facet = controller._obj({"reason": deepcopy(controller.TEXT),
        "status": {"enum": list(STATUSES)},
        "evidence_quotes": {} if inspection else deepcopy(controller.QUOTES)})
    if not inspection:
        facet["properties"]["evidence_quotes"]["items"]["pattern"] = r"\S"
        facet["allOf"] = [{"if": {"properties": {"status": {
            "enum": [status for status in STATUSES if status != "undetermined"]}}, "required": ["status"]},
            "then": {"properties": {"evidence_quotes": {"minItems": 1}}}}]
    row = controller._obj({"id": {"enum": selected} if selected else {"type": "string"},
        "facets": controller._obj({name: deepcopy(facet) for name in FACETS})})
    rows = controller._array(row)
    rows.update(minItems=len(selected), maxItems=len(selected))
    return controller._obj({"originals": rows})


def build_request(source, inventory, eligible_ids=None):
    """Same complete source/inventory payload as guard; no decision fields."""
    selected, catalog = guard._context(source, inventory, eligible_ids)
    payload = {"source": source, "inventory": deepcopy(inventory),
        "eligible_original_ids": selected,
        "source_catalog": [{key: row[key] for key in ("id", "start", "end")} for row in catalog]}
    packet = controller._request(SYSTEM, payload, _schema(selected))
    packet["protocol"] = PROTOCOL
    return packet


def _quote_check(source, quotes, *, decisive):
    """Use the existing exact-quote contract, recording faults rather than raising."""
    try:
        controller._quotes(source, quotes, decisive=decisive)
    except ValueError:
        errors = []
        if type(quotes) is not list:
            return False, [{"code": "quotes_not_list"}]
        if decisive and not quotes:
            errors.append({"code": "decisive_quotes_empty"})
        for index, quote in enumerate(quotes):
            if type(quote) is not str:
                errors.append({"code": "quote_not_string", "quote_index": index})
            elif not quote.strip():
                errors.append({"code": "quote_empty", "quote_index": index})
            elif quote not in source:
                errors.append({"code": "quote_not_exact_source_substring", "quote_index": index})
        guard._require(bool(errors), "Unclassified exact-quote contract failure")
        return False, errors
    return True, []


def assess_response(source, inventory, parsed, eligible_ids=None, legacy=False):
    """Inspect strict facet/ID structure and flag quotes; never apply a decision.

    Legacy decision values are recorded verbatim and ignored, with no presence or
    boolean-type requirement. Only the one explicit alias can be normalized in
    the audit log. Conflicting canonical/alias values are structurally ambiguous.
    """
    guard._require(type(legacy) is bool, "Explicit legacy boolean required")
    selected, _ = guard._context(source, inventory, eligible_ids)
    guard._require(type(parsed) is dict and set(parsed) == {"originals"}
        and type(parsed["originals"]) is list, "Exact originals response object required")
    projection, decisions, mappings = [], [], []
    for raw_row in parsed["originals"]:
        guard._require(type(raw_row) is dict, "Original response row must be an object")
        row = deepcopy(raw_row)
        ignored = {}
        if legacy:
            for key in (*LEGACY_DECISION_KEYS, LEGACY_ALIAS):
                if key in row:
                    ignored[key] = row.pop(key)
            if LEGACY_ALIAS in ignored:
                canonical = LEGACY_DECISION_KEYS[1]
                present = canonical in ignored
                guard._require(not present or controller._digest(ignored[canonical]) ==
                    controller._digest(ignored[LEGACY_ALIAS]), "Ambiguous legacy preservation alias")
                mappings.append({"id": deepcopy(row.get("id")), "from": LEGACY_ALIAS,
                    "to": canonical, "value": deepcopy(ignored[LEGACY_ALIAS]),
                    "canonical_already_present": present})
        projection.append(row)
        decisions.append(ignored)
    projected = {"originals": projection}
    # Quote value/contents are inspected independently; all other structure is strict.
    Draft202012Validator(_schema(selected, inspection=True)).validate(projected)
    ids = [row["id"] for row in projection]
    guard._require(len(ids) == len(set(ids)) and set(ids) == set(selected),
        "Missing, duplicate or foreign facet response IDs")
    originals = []
    for row, ignored in zip(projection, decisions):
        facets = deepcopy(row["facets"])
        for name in FACETS:
            facet = facets[name]
            guard._require(bool(facet["reason"].strip()), "Nonempty facet reason required")
            valid, errors = _quote_check(source, facet["evidence_quotes"],
                decisive=facet["status"] != "undetermined")
            facet.update(quote_valid=valid, quote_errors=errors)
        originals.append({"id": row["id"], "facets": facets,
            "projected_facets": deepcopy(row["facets"]), "legacy_decisions": deepcopy(ignored)})
    return {"protocol": PROTOCOL, "eligible_ids": deepcopy(selected),
        "source_sha256": sha256(source.encode("utf8")).hexdigest(),
        "inventory_sha256": controller._digest(inventory), "parsed_sha256": controller._digest(parsed),
        "projected_sha256": controller._digest(projected), "originals": originals,
        "legacy_mappings": mappings, "binding_is_not_semantic_entailment": True}
