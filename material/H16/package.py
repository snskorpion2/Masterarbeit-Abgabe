"""N16's sixty-item T1 package, using the unchanged offline C7 UI.

The caller owns sampling and its proportional VV-shortfall allocation. This
module preserves its mixed occurrence order and complete native/source values.
No labels, Guard decisions, model calls, or C2 join are needed.
"""
from collections import Counter
from copy import deepcopy
from hashlib import sha256
from pathlib import Path
import secrets

from Experiments.fair_comparison_oct23_v1 import graph_contract as native
from Tools.experiments.c7_human_annotation_oct24_v1 import contracts as c
from Tools.experiments.c7_human_annotation_oct24_v1 import sample as c7
from Tools.experiments.c7_human_annotation_oct24_v1.from_c2 import display_native

PROTOCOL = "H16-N16-T1-human60-v1"
KEY_FORMAT = "h16-private-key-1"
SIZE = 60
SEED = 2026102616
ARMS = ("AS", "V2")
TYPES = ("EE", "EV", "VV")
ROOT = Path(__file__).resolve().parents[1]
HTML_NAME = "H16-Autorenannotation-60.html"


def _hash_text(value):
    return sha256(value.encode("utf8")).hexdigest()


def _quotas(rows, design):
    observed = {arm: {kind: sum(r["arm"] == arm and r["category"] == kind
                               for r in rows) for kind in TYPES} for arm in ARMS}
    c.require(all(sum(counts.values()) == 30 for counts in observed.values()),
              "H16 requires exactly thirty occurrences per arm")
    shortfall = any(counts["VV"] < 10 for counts in observed.values())
    c.require(all(counts["EE"] >= 10 and counts["EV"] >= 10 and counts["VV"] <= 10
                  for counts in observed.values()), "H16 invalid EE/EV/VV quotas")
    if "type_counts" in design:
        declared = design["type_counts"]
        c.require(type(declared) is dict and set(declared) == set(ARMS),
                  "H16 design requires both arm type counts")
        for arm in ARMS:
            c.require(type(declared[arm]) is dict and set(declared[arm]) == set(TYPES)
                      and all(type(n) is int and n >= 0 for n in declared[arm].values()),
                      "H16 design requires strict integer type counts")
        c.require(declared == observed, "H16 declared type counts differ from selected rows")
    if "VV_shortfall_documented" in design:
        c.require(type(design["VV_shortfall_documented"]) is bool
                  and design["VV_shortfall_documented"] is shortfall,
                  "H16 VV-shortfall declaration differs from selected rows")
    c.require(not shortfall or ("type_counts" in design
                               and design.get("VV_shortfall_documented") is True),
              "H16 nonstandard VV quotas require explicit sampler design")


def initial_annotations(packet):
    """Return unanswered technical rows, without claiming human annotation."""
    c.validate_packet(packet)
    return {"format": c.ANNOTATION_FORMAT, "dataset_id": packet["dataset_id"],
            "packet_sha256": packet["packet_sha256"],
            "annotation_origin": "unstarted_template_no_human_labels",
            "annotations": [{"item_id": item["id"], "label": None,
                             "comment": "", "updated_at": None} for item in packet["items"]]}


def _payload(selected_rows, design, provenance, salt, synthetic):
    c.require(type(synthetic) is bool, "H16 explicit synthetic flag required")
    c.require(type(selected_rows) is list and len(selected_rows) == SIZE,
              "H16 requires sixty selected original occurrences")
    c.require(type(design) is dict and type(provenance) is dict,
              "H16 design and provenance must be explicit objects")
    required = {"unit_id", "arm", "category", "source_id", "family", "value",
                "value_sha256", "sources"}
    for row in selected_rows:
        c.require(type(row) is dict and required <= set(row), "H16 original row fields missing")
        c.text(row["unit_id"], "original occurrence ID")
        c.text(row["source_id"], "original owner source ID")
        c.require(row["arm"] in ARMS and row["category"] in TYPES,
                  "H16 unknown arm or native type")
        c.require(row["family"] in {"wikipedia", "factbook"}, "H16 unknown source family")
        c.require(type(row["value"]) is dict, "H16 complete native object required")
    c.require(len({r["unit_id"] for r in selected_rows}) == SIZE,
              "H16 duplicate original occurrence ID")
    _quotas(selected_rows, design)
    salt = c.text(salt, "private H16 blinding salt")

    def opaque(prefix, domain, value):
        return prefix + _hash_text(salt + "|H16-N16|" + domain + "|" + value)[:32]

    dataset_id = opaque("d-", "dataset", c.digest([r["unit_id"] for r in selected_rows]))
    sources, items, private = {}, [], []
    for row in selected_rows:
        value = deepcopy(row["value"])
        upstream_hash = native.digest(value)
        c.require(row["value_sha256"] == upstream_hash, "H16 original native value hash differs")
        statement = display_native(value)
        c.require(type(row["sources"]) is list and bool(row["sources"]),
                  "H16 complete source texts required")
        original_source_ids = []
        for source in row["sources"]:
            c.require(type(source) is dict and {"id", "text", "sha256"} <= set(source),
                      "H16 source fields missing")
            sid = c.text(source["id"], "original source ID")
            text = c.text(source["text"], "full original source text")
            digest = _hash_text(text)
            c.require(source["sha256"] == digest, "H16 source text hash differs")
            c.require(sid not in sources or sources[sid] == {"text": text, "sha256": digest},
                      "H16 source content differs between selected occurrences")
            sources[sid] = {"text": text, "sha256": digest}
            original_source_ids.append(sid)
        c.require(len(original_source_ids) == len(set(original_source_ids)),
                  "H16 duplicate source reference")
        c.require(row["source_id"] in original_source_ids, "H16 original owner source is missing")
        iid = opaque("i-", "item", row["unit_id"])
        items.append({"id": iid, "statement": statement,
                      "source_ids": [opaque("s-", "source", sid) for sid in original_source_ids]})
        private.append({"item_id": iid, "original_id": row["unit_id"], "arm": row["arm"],
            "type": row["category"], "source_id": row["source_id"], "family": row["family"],
            "statement_sha256": _hash_text(statement), "original_value_sha256": c.digest(value),
            "upstream_native_value_sha256": upstream_hash, "original_source_ids": original_source_ids,
            "source_sha256": {sid: sources[sid]["sha256"] for sid in original_source_ids},
            "host_metadata": deepcopy(row)})
    packet = {"format": c.PACKET_FORMAT, "dataset_id": dataset_id, "packet_sha256": "",
        "cohort": "synthetic_test" if synthetic else "confirmation", "items": items,
        "sources": sorted([{"id": opaque("s-", "source", sid), "text": source["text"]}
                           for sid, source in sources.items()], key=lambda item: item["id"])}
    packet["packet_sha256"] = c.packet_digest(packet)
    c.validate_packet(packet)
    key = {"format": KEY_FORMAT, "protocol": PROTOCOL, "dataset_id": dataset_id,
        "packet_sha256": packet["packet_sha256"], "cohort": packet["cohort"], "seed": SEED,
        "selected_count": SIZE, "items": private, "private_blinding_salt": salt,
        "design": deepcopy(design), "provenance": deepcopy(provenance),
        "selected_input_sha256": c.digest(selected_rows), "selection_performed_by_this_module": False,
        "order": "preserved exactly from the external fixed-seed sampler",
        "C7_six_stratum_private_key_contract_used": False,
        "value_hash_definitions": {
            "upstream_native_value_sha256": "graph_contract.digest of complete original native value, ASCII JSON",
            "original_value_sha256": "C7 contracts.digest of unchanged native value, UTF-8 JSON",
            "statement_sha256": "SHA256 of complete display_native statement UTF-8 bytes"},
        "metadata_blinding_boundary": "Private metadata omitted; source content and style remain visible."}
    return packet, key


def _manifest(packet, key, html):
    return {"protocol": PROTOCOL, "dataset_id": packet["dataset_id"],
        "packet_sha256": packet["packet_sha256"], "html_sha256": _hash_text(html),
        "private_key_sha256": c.digest(key), "template_pin": c.file_pin(c7.TEMPLATE),
        "selected_count": SIZE, "source_count": len(packet["sources"]),
        "human_labels_created": 0, "network_or_model_calls": 0, "C7_template_unchanged": True,
        "scientific_exploratory": True, "part_of_primary_Holm_family": False,
        "part_of_overall_judgment": False,
        "technical_cohort_boundary": "C7 'confirmation' is a natural-data container, not a confirmation claim.",
        "sampling_contract": "N16 T1 sixty-item author sample, separate from C7's original study"}


def build_package(selected_rows, design=None, provenance=None, salt=None, synthetic=False):
    """Preserve supplied selection/order; create no labels or additional draw."""
    c.require(design is None or type(design) is dict, "H16 design must be an object")
    c.require(provenance is None or type(provenance) is dict, "H16 provenance must be an object")
    packet, key = _payload(selected_rows, {} if design is None else design,
        {} if provenance is None else provenance,
        secrets.token_hex(32) if salt is None else salt, synthetic)
    html = c7.render(packet)
    return {"packet": packet, "private_key": key, "html": html,
            "initial_annotations": initial_annotations(packet), "manifest": _manifest(packet, key, html)}


def validate_bundle(bundle):
    """Reconstruct all bindings from the preserved original snapshot."""
    c.require(type(bundle) is dict and set(bundle) == {
        "packet", "private_key", "html", "initial_annotations", "manifest"}, "H16 bundle fields differ")
    packet, key = bundle["packet"], bundle["private_key"]
    c.validate_packet(packet)
    c.require(type(key) is dict and key.get("format") == KEY_FORMAT
              and key.get("protocol") == PROTOCOL, "H16 private key contract differs")
    c.require(type(key.get("items")) is list and len(key["items"]) == SIZE
              and all(type(item) is dict and "host_metadata" in item for item in key["items"]),
              "H16 original snapshot incomplete")
    original = [item["host_metadata"] for item in key["items"]]
    expected_packet, expected_key = _payload(original, key["design"], key["provenance"],
        key["private_blinding_salt"], packet["cohort"] == "synthetic_test")
    c.require(c.canonical(packet) == c.canonical(expected_packet)
              and c.canonical(key) == c.canonical(expected_key), "H16 original package binding differs")
    html = c7.render(packet)
    c.require(bundle["html"] == html, "H16 HTML differs from unchanged C7 template")
    c.require(c.canonical(bundle["initial_annotations"]) == c.canonical(initial_annotations(packet)),
              "H16 initial annotations must remain unanswered")
    c.require(c.canonical(bundle["manifest"]) == c.canonical(_manifest(packet, key, html)),
              "H16 manifest binding differs")
    return True


def publish(bundle, public_out, private_out):
    """Write fresh author files and a separate private key, without overwrite."""
    validate_bundle(bundle)
    public_out, private_out = Path(public_out).resolve(), Path(private_out).resolve()
    c.require(public_out != private_out and not private_out.is_relative_to(public_out)
              and not public_out.is_relative_to(private_out), "H16 public/private directories must be separate")
    c.require(not private_out.is_relative_to(ROOT), "H16 private key must remain outside the repository")
    c.require(not public_out.exists() and not private_out.exists(), "H16 fresh output directories required")
    public_out.mkdir(parents=True, exist_ok=False)
    private_out.mkdir(parents=True, exist_ok=False)
    outputs = {public_out / HTML_NAME: bundle["html"].encode("utf8"),
        public_out / "h16.blind.json": c.canonical(bundle["packet"]),
        private_out / "h16.private-key.json": c.canonical(bundle["private_key"]),
        private_out / "h16.package-manifest.json": c.canonical(bundle["manifest"])}
    for path, raw in outputs.items():
        with path.open("xb") as stream:
            stream.write(raw)
    receipt = {"protocol": PROTOCOL, "packet_sha256": bundle["packet"]["packet_sha256"],
        "public_files": [c.file_pin(path) for path in outputs if path.parent == public_out],
        "private_key_pin": c.file_pin(private_out / "h16.private-key.json"),
        "manifest_pin": c.file_pin(private_out / "h16.package-manifest.json"),
        "human_labels_created": 0, "network_or_model_calls": 0}
    with (private_out / "h16.receipt.json").open("xb") as stream:
        stream.write(c.canonical(receipt))
    return receipt
