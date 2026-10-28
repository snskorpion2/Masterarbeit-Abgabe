"""
Canonical triple normalization helpers for extraction and evaluation.
"""

from __future__ import annotations

import re
from copy import deepcopy


def normalize_text(value: object) -> str:
    """Preserve literal content; only actual None represents missing input.

    Future literal-preserving condition: strings are not null sentinels. For
    example, ``Na`` can be a real identifier. Saved runs and their normalization
    contracts are not rewritten by this helper change.
    """
    text = "" if value is None else str(value)
    return re.sub(r"\s+", " ", text.strip())


def _normalize_text(value: object) -> str:
    return normalize_text(value)


def normalize_triple(triple: dict) -> dict:
    """Normalize core fields without dropping category/provenance metadata."""
    subj = triple.get("subject", triple.get("head", triple.get("Head", "")))
    pred = triple.get(
        "predicate",
        triple.get("relation", triple.get("Relation", triple.get("predicate_id", ""))),
    )
    obj = triple.get("object", triple.get("tail", triple.get("Tail", "")))
    pred_id = triple.get("predicate_id", triple.get("property_id", ""))
    return {
        **triple,
        "subject": _normalize_text(subj),
        "predicate": _normalize_text(pred),
        "object": _normalize_text(obj),
        "predicate_id": _normalize_text(pred_id),
    }


def canonical_triple_key(triple: dict) -> tuple[str, str, str]:
    """Return a stable deduplication key for a KG triple.

    We deduplicate on normalized SPO rather than chunk metadata because the KG
    should contain each fact at most once per article even if it appears in
    multiple chunks or is repeated by the model.
    """
    return (
        _normalize_text(triple.get("subject")).casefold(),
        _normalize_text(triple.get("predicate")).casefold(),
        _normalize_text(triple.get("object")).casefold(),
    )


def _occurrence_records(triple):
    """Flatten our own unchanged annotation, preserving later metadata edits."""
    annotation = triple.get("_deduplication")
    current = {key: value for key, value in triple.items() if key != "_deduplication"}
    if (type(annotation) is dict
            and set(annotation) == {"protocol", "records", "representative"}
            and annotation["protocol"] == "typed_exact_record_deduplication:v1"
            and type(annotation["records"]) is list and annotation["records"]
            and type(annotation["representative"]) is dict
            and all(type(row) is dict
                    and canonical_triple_key(row) == canonical_triple_key(triple)
                    and _normalize_text(row.get("triple_type", "")) == _normalize_text(triple.get("triple_type", ""))
                    for row in annotation["records"])):
        records = deepcopy(annotation["records"])
        if current != annotation["representative"]:
            records.append(deepcopy(current))
        return records
    return [deepcopy(triple)]


def dedupe_triples(triples: list[dict]) -> list[dict]:
    """Deduplicate triples while preserving first-seen order.

    Only same-category lexical SPO duplicates are combined. Conflicting
    explicit predicate IDs remain distinct, with ambiguous missing IDs kept
    separate. No alias or semantic fusion is performed. Each supplied occurrence (and any later
    metadata revision) remains separately recoverable in ``_deduplication``.
    The representative keeps the existing richer-PID/max-confidence behavior.
    """
    deduped: list[dict] = []
    by_key: dict[tuple, dict] = {}
    known_pids: dict[tuple, set[str]] = {}
    for triple in triples:
        if isinstance(triple, dict):
            scope = (_normalize_text(triple.get("triple_type", "")), canonical_triple_key(triple))
            pid = _normalize_text(triple.get("predicate_id", ""))
            if pid:
                known_pids.setdefault(scope, set()).add(pid)

    for triple in triples:
        if not isinstance(triple, dict):
            continue

        # Do not silently turn missing/unknown category metadata into EE.
        scope = (_normalize_text(triple.get("triple_type", "")), canonical_triple_key(triple))
        key = (scope, _normalize_text(triple.get("predicate_id", ""))
               if len(known_pids.get(scope, ())) > 1 else "")
        existing = by_key.get(key)
        if existing is None:
            kept = deepcopy(triple)
            deduped.append(kept)
            by_key[key] = kept
            continue

        occurrences = _occurrence_records(existing) + _occurrence_records(triple)
        for field, value in triple.items():
            if field not in existing and field not in {
                "_deduplication", "confidence", "confidence_score"
            }:
                existing[field] = deepcopy(value)

        if not existing.get("predicate_id") and triple.get("predicate_id"):
            existing["predicate_id"] = triple["predicate_id"]

        new_confidence = triple.get("confidence")
        old_confidence = existing.get("confidence")
        if new_confidence is not None:
            try:
                new_value = float(new_confidence)
                old_value = (
                    float(old_confidence) if old_confidence is not None else -1.0
                )
                if new_value > old_value:
                    existing["confidence"] = new_value
                    # The native 0..1 value and 0..10 score describe the same
                    # selected occurrence. Never combine scores from different
                    # records; missing winner scores remain explicitly absent.
                    if triple.get("confidence_score") is not None:
                        existing["confidence_score"] = deepcopy(triple["confidence_score"])
                    else:
                        existing.pop("confidence_score", None)
                    if triple.get("verdict"):
                        existing["verdict"] = triple["verdict"]
            except (TypeError, ValueError):
                pass

        if not existing.get("verdict") and triple.get("verdict"):
            existing["verdict"] = triple["verdict"]

        existing["_deduplication"] = {
            "protocol": "typed_exact_record_deduplication:v1",
            "records": occurrences,
            "representative": deepcopy({key: value for key, value in existing.items() if key != "_deduplication"}),
        }

    return deduped

