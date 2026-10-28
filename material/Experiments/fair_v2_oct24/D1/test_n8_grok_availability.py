"""N8 availability regression over invented, normalized full-pipeline inputs."""
from copy import deepcopy

import pytest

from Experiments.fair_v2_oct24.D1.analysis import analyze
from Experiments.fair_v2_oct24.D1.contract import load_contract
from Experiments.fair_v2_oct24.D1.native import normalize_native
from Experiments.fair_v2_oct24.D1.synthetic import build_native_fixture


@pytest.fixture(scope="module")
def synthetic_inputs():
    # load_contract reads published contract metadata, never outcome bindings.
    contract = load_contract()
    raw = build_native_fixture(sources=contract["sources"], qa_blocks=contract["qa_blocks"])
    raw["question_ids"] = list(contract["question_ids"])
    return raw, contract


def _bundle(raw, mode):
    """Keep original IDs/membership while inventing C2/C4 countercheck states."""
    raw = deepcopy(raw)
    core_ids = {r["unit_id"] for r in raw["C4"] if r["in_base_sample"]}
    missing_core_reference = mode != "undefined_with_pairs"
    raw["C7"] = None  # Isolate C4; absent human checking remains explicitly missing.

    def set_c2(row):
        missing = missing_core_reference and row["unit_id"] in core_ids
        code = None if missing else "unsupported" if row["arm"] == "AS" else "supported"
        label = None if missing else "not_supported" if row["arm"] == "AS" else "supported"
        row.update(raw_code=code, label=label,
                   measurement_status="technical_missing" if missing else "valid",
                   primary_numeric=int(label == "supported"),
                   H1_bucket="M" if missing else "F" if label == "not_supported" else "S",
                   unknown_execution=None if missing else False)
        return code, missing

    originals = {}
    for row in raw["C2"]["occurrence_labels"]:
        originals[row["unit_id"]] = set_c2(row)
    for cell in raw["C2"]["cells"]:
        for row in cell["labels"]:
            set_c2(row)
    for row in raw["C4"]:
        code, missing = originals[row["unit_id"]]
        row.update(c2_code=code, c2_status="technical_missing" if missing else "rated")
        if row["in_base_sample"]:
            # Same labels across both parents produce zero; otherwise Grok
            # prefers AS, opposite to the invented primary V2-minus-AS gain.
            row.update(grok_code="supported" if mode == "zero" or row["arm"] == "AS"
                       else "unsupported", grok_status="rated")
            if mode == "undefined_with_pairs":
                row["weight"] = None
        else:
            # Nonrepresentative removal augmentation cannot manufacture pairs.
            row.update(grok_code=None, grok_status="missing")
    if mode == "absent":
        raw["C4"] = []
    return normalize_native(raw)


def test_opposite_grok_direction_qualifies_h1_even_without_sol_grok_pairs(synthetic_inputs):
    raw, contract = synthetic_inputs
    bundle = _bundle(raw, "opposite")
    before = deepcopy(bundle)
    result = analyze(bundle, contract)
    assert bundle == before
    grok = result["agreement"]["grok"]
    assert grok["N_pair"] == 0 and grok["kappa"] is None
    assert grok["directional_sensitivity"]["direction"]["point_difference"] == -1
    assert result["primary"]["H1"]["point_difference"] > 0
    judgment = result["overall_judgment"]
    assert judgment["counterchecks"]["C4"]["available"] is True
    assert "C4" not in judgment["missing_counterchecks"]
    assert judgment["dependence_reasons"] == ["C4_opposite_H1_point_estimate_sign"]
    assert judgment["H1_qualification"] == "bewerterabhängig"
    for name in ("guard_AS", "guard_V1", "extraction_extension"):
        assert result["components"]["verdicts"][name]["H1_qualification"] == "bewerterabhängig"


def test_zero_grok_direction_is_available_without_becoming_opposite(synthetic_inputs):
    raw, contract = synthetic_inputs
    result = analyze(_bundle(raw, "zero"), contract)
    grok = result["agreement"]["grok"]
    assert grok["N_pair"] == 0
    assert grok["directional_sensitivity"]["direction"]["point_difference"] == 0
    judgment = result["overall_judgment"]
    assert judgment["counterchecks"]["C4"]["available"] is True
    assert "C4" not in judgment["missing_counterchecks"]
    assert judgment["evaluator_dependent"] is False
    assert judgment["dependence_reasons"] == []


@pytest.mark.parametrize("mode,has_pairs", [("absent", False), ("undefined_with_pairs", True)])
def test_undefined_grok_direction_is_missing_regardless_of_nominal_pairs(
        synthetic_inputs, mode, has_pairs):
    raw, contract = synthetic_inputs
    result = analyze(_bundle(raw, mode), contract)
    grok = result["agreement"]["grok"]
    assert (grok["N_pair"] > 0) is has_pairs
    sensitivity = grok["directional_sensitivity"]
    assert sensitivity is None or sensitivity["direction"]["point_difference"] is None
    judgment = result["overall_judgment"]
    assert judgment["counterchecks"]["C4"]["available"] is False
    assert "C4" in judgment["missing_counterchecks"]
    assert judgment["evaluator_dependent"] is False
    assert judgment["counterchecks_confirm_independence"] is False
