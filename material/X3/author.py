"""Aggregate the unchanged fixed H12 author sample for exploratory X3.

Only explicitly supplied in-memory inputs are consumed. No files, models,
statistical tests, bootstrap, new labels or population estimates are used.
"""
from collections import Counter
import re

from Experiments.fair_v2_oct24.H12 import evaluate as h12
from Tools.experiments.c7_human_annotation_oct24_v1.contracts import validate_annotations


PROTOCOL = "X3-H12-fixed90-intersections:v1"
GROUPS = (
    ("vv_still_removed", "VV weiterhin entfernt"),
    ("ee_removal_reversed", "EE-Entfernung zurückgenommen"),
    ("retained_controls_unchanged", "behaltene Kontrollen unverändert"),
)


def _need(condition, message):
    if not condition:
        raise ValueError("X3_AUTHOR_" + message)


def _text(value):
    return type(value) is str and bool(value.strip())


def _ids(value):
    _need(type(value) is list and all(_text(uid) for uid in value), "ID_LIST_REQUIRED")
    _need(len(value) == len(set(value)), "DUPLICATE_MEMBERSHIP_UID")
    return set(value)


def _draw(value):
    if type(value) is int and value > 0:
        return value
    _need(type(value) is str and re.fullmatch(r"draw_[1-9][0-9]*", value),
          "EXPLICIT_POSITIVE_DRAW_REQUIRED")
    return int(value[5:])


def _memberships(memberships):
    """Validate all 136 parents and return a private UID ownership index.

    kept_ids is the NEW VV-only inventory, in original order. Original kept
    controls are original_unit_ids minus full_removed_ids. No IDs are returned
    by the public summary function.
    """
    _need(type(memberships) is list and len(memberships) == 136,
          "COMPLETE_136_PARENT_SCOPE_REQUIRED")
    parents, ownership, source_draw_arms = set(), {}, {}
    for row in memberships:
        _need(type(row) is dict, "PARENT_MAPPING_REQUIRED")
        parent, source, arm = row.get("parent_id"), row.get("source_id"), row.get("arm")
        _need(_text(parent) and parent not in parents and _text(source)
              and arm in ("AS", "V1"), "UNIQUE_PARENT_SOURCE_ARM_REQUIRED")
        parents.add(parent)
        draw = _draw(row.get("draw"))
        key = source, draw
        arms = source_draw_arms.setdefault(key, set())
        _need(arm not in arms, "DUPLICATE_SOURCE_DRAW_ARM")
        arms.add(arm)
        original = _ids(row.get("original_unit_ids"))
        categories = row.get("categoriesByUnitId")
        _need(type(categories) is dict and set(categories) == original
              and all(c in ("EE", "EV", "VV") for c in categories.values()),
              "EXACT_ORIGINAL_CATEGORY_MAP_REQUIRED")
        removed = _ids(row.get("full_removed_ids"))
        vv = _ids(row.get("vv_removed_ids"))
        ee = _ids(row.get("ee_restored_ids"))
        kept = _ids(row.get("kept_ids"))
        _need(removed <= original and vv.isdisjoint(ee) and removed == vv | ee,
              "ORIGINAL_REMOVAL_PARTITION_DIFFERS")
        _need(all(categories[uid] == "VV" for uid in vv)
              and all(categories[uid] == "EE" for uid in ee),
              "REMOVAL_CATEGORY_DIFFERS")
        _need(kept == original - vv and row["kept_ids"] ==
              [uid for uid in row["original_unit_ids"] if uid not in vv],
              "NEW_KEPT_MEMBERSHIP_OR_ORDER_DIFFERS")
        if "full_kept_ids" in row:
            _ids(row["full_kept_ids"])
            _need(row["full_kept_ids"] ==
                  [uid for uid in row["original_unit_ids"] if uid not in removed],
                  "ORIGINAL_KEPT_MEMBERSHIP_DIFFERS")
        for uid in original:
            _need(uid not in ownership, "GLOBAL_UID_HAS_MULTIPLE_PARENTS")
            ownership[uid] = {
                "parent_id": parent, "source_id": source, "arm": arm, "draw": draw,
                "category": categories[uid], "originally_removed": uid in removed,
                "vv_removed": uid in vv, "ee_restored": uid in ee,
                "new_kept": uid in kept,
            }
    _need(len(source_draw_arms) == 68
          and len({sid for sid, _ in source_draw_arms}) == 24
          and all(arms == {"AS", "V1"} for arms in source_draw_arms.values()),
          "COMPLETE_24_SOURCE_68_PAIR_SCOPE_REQUIRED")
    return ownership


def _group(item, owner):
    host = item.get("host_metadata")
    _need(type(host) is dict, "ORIGINAL_H12_HOST_REQUIRED")
    _need(host.get("unit_id") == item["original_id"]
          and host.get("arm") == item["arm"] == owner["arm"]
          and host.get("source_id") == item["source_id"] == owner["source_id"]
          and host.get("parent_id") == owner["parent_id"]
          and _draw(host.get("draw")) == owner["draw"]
          and host.get("category") == item["type"] == owner["category"],
          "ORIGINAL_UID_SOURCE_ARM_DRAW_PARENT_TYPE_DIFFERS")
    _need(host.get("guard_decision") == item["guard_decision"]
          and host.get("guard_assessed") is True
          and host.get("triggering_facets") == item["triggering_facets"]
          and bool(item["triggering_facets"]) == (item["guard_decision"] == "removed")
          and owner["originally_removed"] == (item["guard_decision"] == "removed"),
          "ORIGINAL_GUARD_DECISION_DIFFERS")
    if item["guard_decision"] == "retained":
        _need(owner["new_kept"], "ORIGINAL_CONTROL_NOT_RETAINED")
        return "retained_controls_unchanged"
    if item["type"] == "VV":
        _need(owner["vv_removed"] and not owner["new_kept"], "VV_REMOVAL_DIFFERS")
        return "vv_still_removed"
    _need(owner["ee_restored"] and owner["new_kept"], "EE_RESTORATION_DIFFERS")
    return "ee_removal_reversed"


def summarize_author(key, annotations, memberships):
    """Return aggregate-only intersections of the original ninety H12 items.

    H12's existing key and annotation validators are reused. Incomplete labels
    stay missing; the complete fixed sample and every UID ownership binding
    remain mandatory. Human confirmation comes from the caller's bound H12
    handoff, while this function validates its human_ui_input origin marker.
    """
    items = h12._key(key)
    _need(type(annotations) is dict
          and annotations.get("annotation_origin") == "human_ui_input",
          "ORIGINAL_HUMAN_UI_ORIGIN_REQUIRED")
    ratings = validate_annotations(
        annotations, dataset_id=key["dataset_id"], packet_sha256=key["packet_sha256"],
        item_ids=[item["item_id"] for item in items])
    ownership = _memberships(memberships)
    labels = {item["item_id"]: ratings.get(item["item_id"], {}).get("label") for item in items}
    grouped = {(group, arm): [] for group, _ in GROUPS for arm in ("AS", "V1", "overall")}
    for item in items:
        _need(item["original_id"] in ownership, "SAMPLE_UID_MISSING_FROM_MEMBERSHIP")
        group = _group(item, ownership[item["original_id"]])
        grouped[group, item["arm"]].append(item)
        grouped[group, "overall"].append(item)
    output = {}
    for group, description in GROUPS:
        arms = {}
        for arm in ("AS", "V1", "overall"):
            selected = grouped[group, arm]
            counts = Counter(labels[item["item_id"]] for item in selected)
            row = {"N": len(selected), "not_supported_count": counts["not_supported"],
                   "supported_count": counts["supported"], "unclear_count": counts["unclear"],
                   "missing_count": counts[None], "complete": counts[None] == 0}
            if group == "vv_still_removed":
                row.update(precision=h12._rate(selected, labels)["rate"],
                           precision_denominator=len(selected),
                           precision_definition="not_supported / all fixed H12 items in this intersection",
                           unclear_counts_as_not_supported=False,
                           precision_scope="VV removal subsample, no population prevalence")
            arms[arm] = row
        output[group] = {"description": description, "by_arm": arms}
    return {
        "protocol": PROTOCOL, "classification": "nachträglich, explorativ",
        "post_hoc": True, "exploratory": True, "fixed_sample_size": 90,
        "complete_author_export": all(label in h12.LABELS for label in labels.values()),
        "annotation_origin": "human_ui_input",
        "missing_annotation_rows": sum(item["item_id"] not in ratings for item in items),
        "null_author_labels": sum(row["label"] is None for row in ratings.values()),
        "membership_scope": {"parents": 136, "sources": 24, "source_draw_pairs": 68},
        "intersections": output, "author_labels_modified": False,
        "individual_items_published": False, "population_prevalence_estimated": False,
        "H1_H2_test_performed": False, "overall_judgment_assigned": False,
        "new_model_calls": 0,
    }
