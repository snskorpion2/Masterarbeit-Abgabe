"""One complete-source SCOPE prefix contract, with two fixed approved deltas.

This is prompt/provenance validation only. It dispatches no calls and provides
no evaluator references, obligations or expected outputs to a constructor.
Multi-chunk histories are deliberately unsupported by this one-unit contract.
"""
from copy import deepcopy
from hashlib import sha256
from pathlib import Path

from . import supplement as previous


PROTOCOL = "fair-as-scope-ev-vv-prefix-oct23-v1"
PRODUCER_RELATIVE_PATH = "Tools/experiments/source_binding_oct23_v1/event_scope_job.py"
PRODUCER_SHA256 = "274cbab8f88abb4a5ddbd5888645d3bf56e5bc7af7a680d99b83f780518aabb7"
CONFIG_SHA256 = "71fa11413f83c6f9079d2650025b16d1e669638469a66788f42fc72e0bbadfe1"
CLAUSES = {
    "event": (
        "Each whole Event together with its Entity list must faithfully express what the "
        "source states about that event occurrence. Preserve participant roles and "
        "qualifications that change the assertion, including attribution, uncertainty, "
        "negation, modality, intention, conditions and temporal scope. Do not turn a "
        "restricted participant group, a purpose, a possibility or a reported claim into "
        "an unqualified actual event. Preserve qualified source information in the Event "
        "sentence rather than dropping it. Do not add participants, roles or outcomes "
        "from background knowledge or mere proximity."),
    "relation": (
        "Read each complete object as Head + Relation + Tail. Both event descriptions and "
        "their particular link must jointly follow from the source, including direction "
        "and qualifications. Correct endpoints alone do not establish a temporal or "
        "causal link. Read because with the reason in Tail, and as a result with the "
        "result in Tail. Preserve attribution, uncertainty, negation, modality, intention "
        "and conditions within the appropriate event sentences; a purpose or possible "
        "outcome does not establish actual occurrence or causation. Unambiguous calendar "
        "dates of these same events may support temporal order. Mere mention order or "
        "co-occurrence does not establish a link. Extract meaningful supported relations; "
        "an empty array is valid when none are supported.")}
CLAUSE_SHA256 = {
    "event": "40d521b9313462bb127b851202079a6db9e833c51f844bc8cbc62a982e35e493",
    "relation": "3827ac570a7eaabf07f12ab095bf52d6d0a8eaa14f814cd13808f02b06b08043"}


def producer_binding():
    path = Path(__file__).resolve().parents[2] / PRODUCER_RELATIVE_PATH
    if sha256(path.read_bytes()).hexdigest() != PRODUCER_SHA256:
        raise ValueError("Approved SCOPE producer code differs")
    return {"path": str(path), "sha256": PRODUCER_SHA256}


def _messages(source_bytes):
    if type(source_bytes) is not bytes:
        raise TypeError("Exact UTF8 source bytes required")
    text = source_bytes.decode("utf8", errors="strict")
    if not text.strip():
        raise ValueError("Nonempty complete source unit required")
    batches = previous.original.native_extraction_prompts(text)
    modified = deepcopy(batches)
    for category, messages in zip(previous.original.CATEGORIES, modified):
        if category in CLAUSES:
            clause = CLAUSES[category]
            if sha256(clause.encode("utf8")).hexdigest() != CLAUSE_SHA256[category]:
                raise ValueError("Approved SCOPE clause bytes differ")
            if not messages or messages[0].get("role") != "system":
                raise ValueError("Original SCOPE system message required")
            messages[0]["content"] += "\n\n" + clause
    return batches, modified


def scope_prefix_condition(source_bytes):
    """Construct the sole accepted optional condition from exact source bytes.

    No caller-defined clause, messages, category order or chunk selection is
    accepted. Only EV/VV system suffixes differ from the Original prompts.
    """
    original, scoped = _messages(source_bytes)
    condition = {"protocol": PROTOCOL,
                 "source_sha256": sha256(source_bytes).hexdigest(),
                 "source_utf8_bytes": len(source_bytes), "source_unit_count": 1,
                 "native_prefix_request_count": 3,
                 "original_extraction_request_count": 1,
                 "modified_extraction_request_count": 2,
                 "producer_binding": producer_binding(),
                 "approved_clause_config_sha256": CONFIG_SHA256,
                 "stages": []}
    for category, before, after in zip(previous.original.CATEGORIES, original, scoped):
        clause = CLAUSES.get(category)
        condition["stages"].append({"category": category,
            "delta": "system_append_LF_LF_clause" if clause else "unchanged_original",
            "clause": clause, "clause_sha256": CLAUSE_SHA256.get(category),
            "original_messages_sha256": previous._digest(before),
            "actual_messages_sha256": previous._digest(after)})
    condition["condition_sha256"] = previous._digest(condition)
    return condition


def validate_scope_prefix(source_bytes, native_row, history, condition, *, native_classifier):
    """Validate the fixed condition, actual unchanged history and whole values."""
    expected = scope_prefix_condition(source_bytes)
    if type(condition) is not dict or previous._digest(condition) != previous._digest(expected):
        raise ValueError("SCOPE prefix condition differs from fixed source-bound policy")
    _original, messages = _messages(source_bytes)
    return previous._validate_prefix_messages(source_bytes, native_row, history,
        native_classifier=native_classifier, expected_messages=messages)
