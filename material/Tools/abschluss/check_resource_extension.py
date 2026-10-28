"""Read-only optional resource addendum, not an experiment scheduler or cost receipt."""
from __future__ import annotations
import argparse
from copy import deepcopy
from decimal import Decimal, InvalidOperation
import hashlib
import json
from pathlib import Path

VERSION = "thesis-resource-extension:1"
VERSION_V2 = "thesis-resource-extension:2"
WSE_PENDING_V2 = {"authorization": "user_authorized", "usable": False,
                  "remote_preflight_required": True, "readiness_verified": False,
                  "queue": "user_reported_pending", "requires_separate_bounded_execution_plan": True,
                  "stop_other_users_jobs": False, "budget_reset": False}
BASE_KEYS = ("approved_on", "submission_due", "submission_mode", "scope", "resources", "experiment_contract", "milestones")
GUARDS = {"frozen_experiment_plans_unchanged": True, "existing_accounting_preserved": True,
          "budget_reset_allowed": False, "implicit_new_experiment_authorization": False,
          "implicit_cohort_sampling_or_ablation_expansion": False,
          "scientific_gates_completed_by_resource_extension": False, "unknown_costs_are_zero": False}
AZURE = {"authorization": "approved_bounded", "model": "Kimi-K2.6", "deployment_type": "GlobalStandard",
         "billing": "consumption_per_token", "credit_usd": 200, "initial_pilot_cap_usd": 20,
         "reserve_usd": 40, "later_phase_cap_usd": 140, "later_phase_released": False,
         "credit_coverage_verified": False, "pricing_verified": False,
         "uncovered_external_spend_allowed": False, "PTU_allowed": False, "server_hours_allowed": False}


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def baseline_contract(plan):
    return deepcopy({**{k: plan[k] for k in BASE_KEYS}, "gate_deadlines": {g["id"]: g["due"] for g in plan["gates"]},
                     "review_deadlines": {r["name"]: r["return_due"] for r in plan["reviewers"]}})


def money(value):
    if value is None or isinstance(value, bool):
        raise ValueError("Unknown money is not zero; finite nonnegative amount required")
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError("Finite nonnegative money required") from exc
    if not amount.is_finite() or amount < 0:
        raise ValueError("Finite nonnegative money required")
    return amount


def validate(extension, root):
    root = Path(root).resolve()
    version = extension.get("schema_version")
    if version not in (VERSION, VERSION_V2) or extension.get("approved_on") != "2026-10-12":
        raise ValueError("Explicit approved extension version/date required")
    base = extension["baseline"]
    if base["path"] != "Tools/abschluss/plan.json" or base["approved_on"] != "2026-10-11":
        raise ValueError("Original approved baseline required")
    plan = json.loads((root / base["path"]).read_bytes())
    if hashlib.sha256(canonical(baseline_contract(plan))).hexdigest() != base["contract_sha256"]:
        raise ValueError("Baseline scope, resources, cohort, sampling, ablation or deadlines changed")
    if (base["local_total_hours"], base["local_reserve_hours"]) != (48, 12):
        raise ValueError("Original local budget cannot be reset or expanded")
    expected = {"Tools/abschluss/continuation_budget_2026-10-12.json", "Tools/abschluss/accounting_checkpoint_2026-10-12.json"}
    if set(base["budget_snapshot_canonical_json_bindings"]) != expected:
        raise ValueError("Existing consumed and unknown local allocations must remain bound")
    for name, digest in base["budget_snapshot_canonical_json_bindings"].items():
        if hashlib.sha256(canonical(json.loads((root / name).read_bytes()))).hexdigest() != digest:
            raise ValueError("Existing accounting snapshot changed")
    resources = extension["resources"]
    if set(resources) != {"local_PC", "HAWKI2", "MicrosoftFoundry", "gpu_server_a", "gpu_server_b"}:
        raise ValueError("Only explicitly named resources allowed")
    if canonical(resources["MicrosoftFoundry"]) != canonical(AZURE) or canonical(extension["guards"]) != canonical(GUARDS):
        raise ValueError("Approved cloud model, billing, phases, reserves or scope guards changed")
    if resources["local_PC"] != {"authorization": "inherited_unchanged", "budget_reset": False}:
        raise ValueError("Local budget remains inherited, not renewed")
    for name in ("gpu_server_a", "gpu_server_b"):
        expected_remote = ({"authorization": "pending_user_confirmation", "usable": False}
                           if version == VERSION else WSE_PENDING_V2)
        if canonical(resources[name]) != canonical(expected_remote):
            raise ValueError("Frozen remote authorization/readiness guards changed; no implicit jobs or budget reset")
    hawki = resources["HAWKI2"]
    if hawki != {"authorization": "approved", "host": "https://hawki2.htwk-leipzig.de", "usage_tokens": None,
                 "cost_usd": None, "unknown_is_zero": False, "requires_separate_bounded_execution_plan": True}:
        raise ValueError("HAWKI unknown metering must not be replaced with zero")
    deadlines = {"measurement_contract": "2026-10-13", "experiment_cutoff": "2026-10-17",
                 "complete_draft": "2026-10-18", "human_review_return": "2026-10-23", "submission": "2026-10-31"}
    if extension["unchanged_deadlines"] != deadlines:
        raise ValueError("Approved closure deadlines remain unchanged")
    return {"resource_addendum_valid": True, "new_experiment_authorized": False, "scientific_gate_completed": False}


def check_proposal(extension, proposal, accounting=None, release=None):
    """Cost ceiling check only. The caller must first validate the bound addendum."""
    resource = proposal.get("resource")
    if resource in ("gpu_server_a", "gpu_server_b") and extension.get("schema_version") == VERSION_V2:
        # V2 records user permission, not a measured readiness/dispatch release.
        # Proposal booleans cannot replace primary preflight evidence and a
        # separately approved bounded execution plan. This helper starts no job.
        raise ValueError("WSE user-authorized but readiness unverified: fresh remote preflight evidence and a separate bounded execution plan required")
    if resource not in ("local_PC", "HAWKI2", "MicrosoftFoundry"):
        raise ValueError("Unapproved or pending resource")
    if proposal.get("scope_expansion", False) is not False:
        raise ValueError("Resource authorization does not expand the experimental scope")
    if resource != "MicrosoftFoundry":
        return {"resource_allowed": True, "execution_authorized": False, "measured_cost_usd": None}
    az = extension["resources"][resource]
    if any(proposal.get(k) != az[k] for k in ("model", "deployment_type", "billing")):
        raise ValueError("Only Kimi-K2.6 with token-billed GlobalStandard allowed")
    if any(proposal.get(k) is not True for k in ("credit_coverage_verified", "pricing_verified")) or proposal.get("uncovered_external_spend", False) is not False:
        raise ValueError("Verified covered credit and pricing required; no external spending")
    if not accounting or set(accounting) != {"spent_credit_usd", "outstanding_reserved_usd", "pilot_spent_usd", "later_phase_spent_usd"}:
        raise ValueError("Complete non-reset accounting including pending calls required")
    spent, reserved, pilot, later = (money(accounting[k]) for k in ("spent_credit_usd", "outstanding_reserved_usd", "pilot_spent_usd", "later_phase_spent_usd"))
    proposed = money(proposal.get("max_spend_usd"))
    if proposed <= 0 or pilot + later > spent or spent + reserved > money(az["credit_usd"]):
        raise ValueError("Invalid conservative cost accounting")
    available = money(az["credit_usd"]) - spent - reserved - money(az["reserve_usd"])
    if proposed > available:
        raise ValueError("Proposal exceeds remaining credit minus protected reserve")
    phase = proposal.get("phase")
    if phase == "initial_pilot":
        if pilot + reserved + proposed > money(az["initial_pilot_cap_usd"]):
            raise ValueError("Initial pilot ceiling includes all pending reservations")
    elif phase == "later_phase":
        if not release or any(release.get(k) is not True for k in ("measured_pilot_costs_verified", "pilot_quality_checked", "explicit_release_approved")):
            raise ValueError("Later phase requires measured pilot costs, quality check and explicit release")
        if later + reserved + proposed > money(az["later_phase_cap_usd"]):
            raise ValueError("Later-phase ceiling exceeded")
    else:
        raise ValueError("Explicit pilot or later phase required")
    return {"resource_allowed": True, "cost_ceiling_check_passed": True, "execution_authorized": False,
            "remaining_credit_minus_reserve_usd": str(available), "max_spend_usd": str(proposed)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--extension", type=Path, default=Path(__file__).with_name("resource_extension_oct12_v1.json"))
    args = parser.parse_args()
    print(json.dumps(validate(json.loads(args.extension.read_bytes()), Path(__file__).resolve().parents[2]), indent=2))


if __name__ == "__main__":
    main()
