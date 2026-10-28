"""Prospective N16 author evaluation, with no discovery or provider access.

The fixed, unweighted 30+30 statement sample is the estimand. 10,000 independent
within-arm statement bootstraps use PCG64 seed 2026102617 and linear 95% percentile
intervals. This is not a paired-statement or source-cluster bootstrap. No source,
construction, or selection dependence is corrected. No Holm test, kappa, or
overall pipeline decision is calculated.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import re
import stat

import numpy as np

from Tools.experiments.c7_human_annotation_oct24_v1 import contracts as c
from Tools.experiments.c7_human_annotation_oct24_v1.evaluate import _strict_json, _write_new_json

PROTOCOL = "H16-N16-T1-human60-v1"
KEY_FORMAT = "h16-private-key-1"
SAMPLE_SEED, CI_SEED, BOOTSTRAP_DRAWS = 2026102616, 2026102617, 10000
ARMS, TYPES, SIZE = ("AS", "V2"), ("EE", "EV", "VV"), 60
MAIN_CONDITION_DIFFERENCE = 0.084
ROOT = Path(__file__).resolve().parents[1]
need = c.require


def _sha(value):
    return type(value) is str and re.fullmatch(r"[0-9a-f]{64}", value) is not None


def _bind(packet, key):
    c.validate_packet(packet)
    need(type(key) is dict and key.get("format") == KEY_FORMAT, "H16 private key required")
    need(key.get("protocol") == PROTOCOL and type(key.get("seed")) is int
         and key["seed"] == SAMPLE_SEED and type(key.get("selected_count")) is int
         and key["selected_count"] == SIZE, "Frozen N16 design required")
    need(key.get("dataset_id") == packet["dataset_id"]
         and key.get("packet_sha256") == packet["packet_sha256"]
         and key.get("cohort") == packet["cohort"], "H16 key/packet binding differs")
    need(type(key.get("design")) is dict and type(key.get("provenance")) is dict,
         "Explicit private design and provenance required")
    items = key.get("items")
    need(type(items) is list and len(items) == len(packet["items"]) == SIZE,
         "Exactly sixty complete packet and key items required")
    public = {row["id"]: row for row in packet["items"]}
    sources = {row["id"]: row["text"] for row in packet["sources"]}
    seen, original, counts, source_map = set(), set(), Counter(), {}
    for row in items:
        need(type(row) is dict, "H16 key item required")
        iid, oid = row.get("item_id"), row.get("original_id")
        need(type(iid) is str and iid in public and iid not in seen,
             "Distinct packet-bound blind IDs required")
        need(type(oid) is str and bool(oid.strip()) and oid not in original,
             "Distinct original occurrence IDs required")
        seen.add(iid)
        original.add(oid)
        need(row.get("arm") in ARMS and row.get("type") in TYPES, "N16 arm/type required")
        counts[row["arm"]] += 1
        source_id, refs = row.get("source_id"), row.get("original_source_ids")
        need(type(source_id) is str and bool(source_id.strip()) and type(refs) is list
             and bool(refs) and all(type(s) is str and s.strip() for s in refs)
             and len(refs) == len(set(refs)) and source_id in refs,
             "Original source owner and unique source references required")
        hashes = row.get("source_sha256")
        need(type(hashes) is dict and set(hashes) == set(refs)
             and all(_sha(h) for h in hashes.values()), "Complete original source hashes required")
        shown = public[iid]
        need(len(refs) == len(shown["source_ids"]), "Source reference count differs")
        for sid, opaque in zip(refs, shown["source_ids"], strict=True):
            need(sid not in source_map or source_map[sid] == opaque,
                 "Original source mapped inconsistently")
            need(opaque not in source_map.values() or source_map.get(sid) == opaque,
                 "Different original sources share a blind ID")
            source_map[sid] = opaque
            need(sha256(sources[opaque].encode("utf8")).hexdigest() == hashes[sid],
                 "Whole source text hash differs")
        statement = shown["statement"]
        need(_sha(row.get("statement_sha256")) and sha256(statement.encode("utf8")).hexdigest()
             == row["statement_sha256"], "Whole displayed statement hash differs")
        value = _strict_json(statement.encode("utf8"))
        need(type(value) is dict and _sha(row.get("original_value_sha256"))
             and c.digest(value) == row["original_value_sha256"],
             "Whole native JSON value hash differs")
    need(seen == set(public) and [counts[a] for a in ARMS] == [30, 30],
         "Exactly thirty statements per arm required")
    return items


def _rate(items, labels, release):
    counts = Counter(labels[row["item_id"]] for row in items)
    n = len(items)
    return {"N": n, "supported_count": counts["supported"],
            "not_supported_count": counts["not_supported"], "unclear_count": counts["unclear"],
            "missing_count": counts[None],
            "supported_rate": counts["supported"] / n if release and n else None,
            "unclear_in_denominator": True, "missing_is_zero_imputed": False}


def _interval(values):
    return {"lower": float(np.quantile(values, .025, method="linear")),
            "upper": float(np.quantile(values, .975, method="linear"))}


def _bootstrap(items, labels):
    rng = np.random.Generator(np.random.PCG64(CI_SEED))
    rates, matrices = {}, []
    for arm in ARMS:
        rows = sorted((row for row in items if row["arm"] == arm), key=lambda r: r["original_id"])
        values = np.asarray([labels[row["item_id"]] == "supported" for row in rows], dtype=float)
        indices = rng.integers(0, 30, size=(BOOTSTRAP_DRAWS, 30), dtype=np.int64)
        rates[arm] = values[indices].mean(axis=1)
        matrices.append({"arm": arm, "N": 30,
                         "matrix_sha256": sha256(indices.astype("<i8").tobytes()).hexdigest()})
    return {"by_arm": {arm: _interval(rates[arm]) for arm in ARMS},
            "difference": _interval(rates["V2"] - rates["AS"]), "matrix_pins": matrices}


def evaluate(packet, key, annotations, author_confirmed=False):
    """Accept explicit objects only. Partial exports release coverage, never rates.

    A complete export still requires direct author confirmation. The origin field
    and local seal assert provenance but cannot authenticate identity or timing.
    """
    items = _bind(packet, key)
    need(author_confirmed is True and type(annotations) is dict
         and annotations.get("annotation_origin") == "human_ui_input",
         "Explicit author confirmation and human_ui_input origin required")
    ratings = c.validate_annotations(annotations, dataset_id=packet["dataset_id"],
                                    packet_sha256=packet["packet_sha256"],
                                    item_ids=[row["item_id"] for row in items])
    labels = {row["item_id"]: ratings.get(row["item_id"], {}).get("label") for row in items}
    complete = all(label in c.LABELS for label in labels.values())
    bootstrap = _bootstrap(items, labels) if complete else None
    rates = {arm: _rate([row for row in items if row["arm"] == arm], labels, complete) for arm in ARMS}
    for arm in ARMS:
        rates[arm]["ci95"] = bootstrap["by_arm"][arm] if complete else None
    delta = rates["V2"]["supported_rate"] - rates["AS"]["supported_rate"] if complete else None
    sign = ("positive" if delta > 0 else "negative" if delta < 0 else "equal") if complete else None
    source_counts = Counter(row["source_id"] for row in items)
    return {"protocol": PROTOCOL, "dataset_id": packet["dataset_id"],
            "packet_sha256": packet["packet_sha256"],
            "status": "complete_author_annotations" if complete else "pending_author_annotations",
            "complete_author_export": complete, "selected_count": SIZE,
            "rated_count": sum(label in c.LABELS for label in labels.values()),
            "missing_annotation_rows": sum(row["item_id"] not in ratings for row in items),
            "null_author_labels": sum(row.get("label") is None for row in ratings.values()),
            "by_arm": rates,
            "difference_V2_minus_AS": {"point": delta, "ci95": bootstrap["difference"] if complete else None,
                                      "direction": sign},
            "main_condition_sign_comparison": {
                "prespecified_main_difference": MAIN_CONDITION_DIFFERENCE,
                "prespecified_main_direction": "positive", "human_sample_direction": sign,
                "same_sign": sign == "positive" if complete else None,
                "comparison_is_descriptive": True, "main_condition_data_reopened": False},
            "by_arm_type": [{"arm": arm, "type": kind,
                **_rate([row for row in items if row["arm"] == arm and row["type"] == kind], labels, complete)}
                for arm in ARMS for kind in TYPES],
            "bootstrap": {"draws": BOOTSTRAP_DRAWS, "seed": CI_SEED, "sampling_seed": SAMPLE_SEED,
                "rng": "numpy.random.Generator(PCG64)", "confidence_level": .95,
                "method": "percentile", "quantile_method": "linear",
                "resampling_unit": "whole_statement_occurrence", "strata": [{"arm": a, "N": 30} for a in ARMS],
                "ordering": "AS then V2; original_id ascending within arm",
                "matrix_hash_encoding": "little-endian int64 C-order",
                "matrix_pins": bootstrap["matrix_pins"] if complete else None,
                "independent_arm_resampling": True, "paired_statement_resampling": False,
                "source_cluster_bootstrap": False, "type_stratified_bootstrap": False},
            "dependence": {"distinct_sources_in_sample": len(source_counts),
                "sources_with_multiple_statements": sum(n > 1 for n in source_counts.values()),
                "maximum_statements_per_source": max(source_counts.values()),
                "source_or_construction_dependence_corrected": False},
            "interpretation": {"exploratory_FF3_only": True, "unweighted_sample_rates": True,
                "population_prevalence_estimate": False, "type_slices_descriptive_only": True,
                "Holm_slots_added": 0, "overall_pipeline_decision": False, "kappa_computed": False,
                "general_transfer_superiority_established": False,
                "annotation_classification": "Autorenannotation",
                "human_identity_authenticated": False, "selection_provenance_authenticated_by_key": False,
                "positive_point_or_same_sign_is_confirmatory_evidence": False},
            "provider_calls": 0}


def evaluate_files(packet_path, key_path, annotation_path, output_path, *, seal_dir, author_confirmed=False):
    """Seal exact export bytes privately before reading the key. Never overwrite.

    The caller supplies every path. A bad input leaves the private original seal
    intact and does not create a public result. No labels or private paths are
    included in the public output.
    """
    need(author_confirmed is True, "Direct author confirmation required")
    packet_path, key_path, annotation_path, output_path, seal_dir = (
        Path(p).resolve() for p in (packet_path, key_path, annotation_path, output_path, seal_dir))
    need(not seal_dir.is_relative_to(ROOT), "Annotation seal must be outside the repository")
    inputs = (packet_path, key_path, annotation_path)
    need(len(set(inputs)) == 3 and output_path not in inputs and output_path != seal_dir,
         "Input, output and seal paths must be distinct")
    need(not output_path.exists() and not seal_dir.exists(), "Refusing overwrite or repeated seal")
    raw_annotations = annotation_path.read_bytes()
    seal_dir.mkdir(parents=True, exist_ok=False)
    snapshot = seal_dir / "author-annotation.original.json"
    with snapshot.open("xb") as target:
        target.write(raw_annotations)
    snapshot.chmod(stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH)
    need(snapshot.read_bytes() == raw_annotations,
         "Private original annotation readback failed before private key read")
    receipt = {"protocol": PROTOCOL, "format": "h16-human-seal-1",
        "sealed_at": datetime.now(timezone.utc).isoformat(),
        "annotation_source_path": str(annotation_path), "snapshot_path": str(snapshot),
        "annotation_bytes": len(raw_annotations), "annotations_sha256": sha256(raw_annotations).hexdigest(),
        "sealed_before_private_key_read": True,
        "limits": "Local byte fingerprint only, no authenticated identity or trusted timestamp"}
    _write_new_json(seal_dir / "author-annotation-seal.json", receipt)
    # Preserve this order: no key read precedes the private original byte seal.
    annotations = _strict_json(raw_annotations)
    raw_packet = packet_path.read_bytes()
    raw_key = key_path.read_bytes()
    report = evaluate(_strict_json(raw_packet), _strict_json(raw_key), annotations,
                      author_confirmed=author_confirmed)
    need(snapshot.read_bytes() == raw_annotations, "Private original annotation seal changed")
    report["input_fingerprints"] = {"packet_file_sha256": sha256(raw_packet).hexdigest(),
        "private_key_file_sha256": sha256(raw_key).hexdigest(),
        "annotation_file_sha256": receipt["annotations_sha256"]}
    report["annotation_seal"] = {"original_bytes_saved_privately": True,
        "sealed_before_private_key_read": True, "snapshot_readback_verified": True,
        "authenticated_identity_or_timestamp": False}
    output_path.parent.mkdir(parents=True, exist_ok=True)
    _write_new_json(output_path, report)
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--packet", required=True)
    parser.add_argument("--key", required=True)
    parser.add_argument("--annotations", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--seal-dir", required=True, help="Fresh private directory outside the repository")
    parser.add_argument("--author-confirmed", action="store_true")
    args = parser.parse_args(argv)
    try:
        report = evaluate_files(args.packet, args.key, args.annotations, args.output,
                                seal_dir=args.seal_dir, author_confirmed=args.author_confirmed)
    except (ValueError, OSError, TypeError) as error:
        parser.exit(2, "H16 evaluation failed: " + str(error) + "\n")
    print(json.dumps({"status": report["status"], "selected_count": report["selected_count"],
                      "output": str(Path(args.output).resolve())}, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
