"""Host-only synthetic development controls for a whole-statement guard.

Thirteen known controls are copied losslessly from existing public fixtures.
Two additional authored controls cover an event-type substitution and a valid
modal EE statement. These are not the historical Grok SS13, fresh natural
confirmation, human gold, or a production relation vocabulary.

Only ``guard_inputs(case)`` is intended for a guard request. Expectations and
provenance remain host-side and must never be passed to a model.
"""
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
VV_FIXTURE = "Tools/experiments/vv_relation_verification_oct23_v1/controls.json"
VV_ADAPTER = "Tools/experiments/vv_relation_verification_oct23_v1/runner.py"
E01_FIXTURE = "Tools/abschluss/e01_native_review_controls_v2.json"
_PINS = {
    VV_FIXTURE: (3395, "9a2bff95ec06eeff28fae7108d13a60ad21d4a86f709f85f9a334085c8910bd5"),
    VV_ADAPTER: (23761, "9018e13905eb25129c3c004a4cf9bcfc993a200d588de3bfb9b8f71d0d096da9"),
    E01_FIXTURE: (58416, "11fcff13e3e5ce1cf1f5fdd54c5dffe8ee4d428eb063fa5e9c67edcf5dd9baad"),
}
KNOWN_VV_IDS = tuple("V%02d" % number for number in range(1, 9))
KNOWN_E01_IDS = ("E01-C001", "E01-C003", "E01-C008", "E01-C027", "E01-C028")
NEW_EVENT_TYPE_ID = "WRG-C014-ACQUISITION-FOR-DONATION"
NEW_MODAL_EE_ID = "WRG-C015-MODAL-EE"


def _pinned_bytes(relative_path):
    raw = (ROOT / relative_path).read_bytes()
    expected_bytes, expected_sha = _PINS[relative_path]
    if len(raw) != expected_bytes or sha256(raw).hexdigest() != expected_sha:
        raise ValueError("Original synthetic control fixture/adapter changed: " + relative_path)
    return raw, {"path": relative_path, "bytes": len(raw), "sha256": expected_sha}


def _source(ident, text, language="en"):
    return {"id": ident, "text": text, "language": language, "format": "prose",
            "sha256": sha256(text.encode("utf-8")).hexdigest()}


def _case(ident, source, native_id, category, value, status, provenance):
    return {
        "id": ident,
        "source": deepcopy(source),
        "inventory": [{"id": native_id, "category": category, "value": deepcopy(value)}],
        "private_expected": {"original_status": status, "keep_expected": status == "supported"},
        "provenance": deepcopy(provenance),
    }


def control_cases():
    """Return fifteen host-side cases; original diagnostic codes stay separate.

    The eight older VV fixtures have no separate native ID. Their existing
    public adapter assigns P1-C0001 through P1-C0008 in fixture order; those
    IDs and the adapter pin are retained explicitly. E01 native IDs and native
    values are copied directly from the original candidate objects.
    """
    raw, vv_pin = _pinned_bytes(VV_FIXTURE)
    vv = json.loads(raw)["cases"]
    _, adapter_pin = _pinned_bytes(VV_ADAPTER)
    if tuple(row["id"] for row in vv) != KNOWN_VV_IDS:
        raise ValueError("Original eight-control order changed")
    cases = []
    for index, row in enumerate(vv, 1):
        native_id = "P1-C%04d" % index
        cases.append(_case(
            row["id"], _source(row["id"] + "-source", row["source"], row["language"]),
            native_id, "VV", row["value"], row["assessment"]["expected_status"],
            {"partition": "known_development", "original_id": row["id"],
             "original_native_id": native_id, "fixture_pin": vv_pin,
             "native_id_origin": "existing_public_adapter_fixture_ordinal",
             "native_id_adapter_pin": adapter_pin,
             "original_status_field": "assessment.expected_status"}))

    raw, e01_pin = _pinned_bytes(E01_FIXTURE)
    e01 = {row["id"]: row for row in json.loads(raw)["source_support"]}
    for ident in KNOWN_E01_IDS:
        row = e01[ident]
        if len(row["expected_codes"]) != 1:
            raise ValueError("Selected original code is no longer a singleton: " + ident)
        native = row["candidate"]
        cases.append(_case(
            ident, row["source"], native["id"], native["category"], native["value"],
            row["expected_codes"][0],
            {"partition": "known_development", "original_id": ident,
             "original_native_id": native["id"], "fixture_pin": e01_pin,
             "original_status_field": "expected_codes[0]"}))

    authored_raw = Path(__file__).read_bytes()
    authored_pin = {"path": Path(__file__).relative_to(ROOT).as_posix(),
                    "bytes": len(authored_raw), "sha256": sha256(authored_raw).hexdigest()}
    authored = {"partition": "new_authored_development", "fixture_pin": authored_pin,
                "human_gold": False, "new_model_calls_to_author": 0,
                "original_status_field": "inline_authored_expectation"}
    cases.append(_case(
        NEW_EVENT_TYPE_ID,
        _source("WRG-S014", "Workshop record: Atelier K completed the vase in 1894. "
                "Donation record: Nora donated the vase to Museum L in 1904. "
                "These records do not state whether or when Nora acquired the vase."),
        "WRG-U014", "VV",
        {"Head": "Atelier K manufactured the vase in 1894.", "Relation": "happened before",
         "Tail": "Nora acquired the vase in 1904."},
        "insufficient", {**authored, "original_id": NEW_EVENT_TYPE_ID,
                         "original_native_id": "WRG-U014"}))
    cases.append(_case(
        NEW_MODAL_EE_ID,
        _source("WRG-S015", "According to the trial, treatment R may reduce nausea in adults; "
                "a cure has not been established."),
        "WRG-U015", "EE",
        {"Head": "treatment R", "Relation": "may reduce in adults", "Tail": "nausea"},
        "supported", {**authored, "original_id": NEW_MODAL_EE_ID,
                      "original_native_id": "WRG-U015"}))
    return cases


def guard_inputs(case):
    """Whitelist model-facing fields; do not forward the host control object."""
    return {key: deepcopy(case[key]) for key in ("id", "source", "inventory")}
