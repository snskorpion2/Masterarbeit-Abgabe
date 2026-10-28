"""New one-request diagnostic version with the existing strict financial gate.

No live execution is authorised by preparing or validating this version. The
old exact request/prompt/model/filter/limits are retained. V1 evidence is read
only. New requests never reuse an already executed V1 reservation. No financial
ledger, addendum, reserve or old adapter is mutated by these functions.
"""
from __future__ import annotations

import argparse
from datetime import datetime
from hashlib import sha256
from http.client import IncompleteRead
from pathlib import Path
import time
from urllib.error import HTTPError
from urllib.request import Request, ProxyHandler, build_opener

from Tools.abschluss import check_resource_extension as resource_check
from Tools.azure import accounting, http_failure_probe_v1 as old
from Tools.azure import response_diagnostics_v2 as diagnostics

HERE = Path(__file__).resolve()
TEST = HERE.parents[1] / "tests/test_azure_response_diagnostics_v2.py"
PROTOCOL = "azure-kimi-one-request-failure-capture:v2"
LIMITS = dict(old.LIMITS)
canonical, digest, unlinked = old.canonical, old.digest, old.unlinked
RESOURCE_EXTENSION = old.MAIN / "Tools/abschluss/resource_extension_oct12_v2.json"


def _read_response(stream):
    """Retain known HTTP status even when reading its bounded body fails."""
    try:
        raw = stream.read(262145)
        return raw, isinstance(raw, bytes) and len(raw) <= 262144
    except IncompleteRead as error:
        partial = error.partial if isinstance(error.partial, bytes) else b""
        return partial[:262145], False
    except Exception:
        return b"", False


def azure_wire(config, payload, *, timeout):
    # Byte-identical request serialization/headers and unchanged routing policy.
    request = Request(config.url, data=canonical(payload), method="POST", headers={
        "api-key": config.key, "Accept": "application/json", "Content-Type": "application/json"})
    opener = build_opener(ProxyHandler({}), old.controls.quote.base.old.v1.probe.NoRedirect())
    with opener.open(request, timeout=timeout) as response:
        raw, complete = _read_response(response)
        return response.status, raw, complete


def budget_check(*, resource_extension_path, proposal_path, accounting_path, release_path=None):
    """Both existing gates, never validate-only, unknown-as-zero or a phase release."""
    paths = {"resource_extension_path": resource_extension_path,
             "proposal_path": proposal_path, "accounting_path": accounting_path}
    if release_path is not None:
        paths["release_path"] = release_path
    values, bindings = {}, []
    for name, path in paths.items():
        raw = unlinked(path).read_bytes()
        if len(raw) > 65536:
            raise ValueError("Bounded financial input required")
        values[name] = old.controls.quote.base.old.v1.probe._strict_json(raw)
        if type(values[name]) is not dict:
            raise ValueError("Explicit financial input objects required")
        bindings.append(old.controls.quote.base.old.v1.common.binding(path))
    validated = resource_check.validate(values["resource_extension_path"], old.MAIN)
    proposal = values["proposal_path"]
    if (proposal.get("resource") != "MicrosoftFoundry" or proposal.get("phase") != "initial_pilot"
            or resource_check.money(proposal.get("max_spend_usd")) != resource_check.money(2)):
        raise ValueError("Same bounded two-dollar diagnostic proposal required")
    checked = resource_check.check_proposal(values["resource_extension_path"], proposal,
        values["accounting_path"], values.get("release_path"))
    return {**checked, "addendum_validation": validated,
        "input_bindings": bindings, "budget_state_modified": False,
        "inputs": {name: str(unlinked(path)) for name, path in paths.items()}}, values["accounting_path"]


def prepare(run_output, env_path=old.controls.quote.base.old.v1.probe.DEFAULT_ENV, *,
            resource_extension_path=RESOURCE_EXTENSION, proposal_path, accounting_path, release_path=None):
    guard, counters = budget_check(resource_extension_path=resource_extension_path,
        proposal_path=proposal_path, accounting_path=accounting_path, release_path=release_path)
    # Gate before credentials or the inherited preparation, not only before wire.
    previous, raw = old.prepare(run_output, env_path)
    body = {key: value for key, value in previous.items() if key != "plan_sha256"}
    prior_reserved = resource_check.money(counters["outstanding_reserved_usd"])
    proposed = resource_check.money(2)
    body.update(protocol=PROTOCOL, inherited_v1_preparation_sha256=previous["plan_sha256"],
        budget_guard=guard, financial_guard_code_binding=old.controls.quote.base.old.v1.common.binding(resource_check.__file__),
        own_code_and_tests=[*previous["own_code_and_tests"], *[
            old.controls.quote.base.old.v1.common.binding(path) for path in (HERE, diagnostics.HERE, TEST)]],
        historical_v1_reservation_reused=False, budget_state_modified=False,
        response_diagnostic_protocol=diagnostics.PROTOCOL,
        new_execution_requires_separate_explicit_approval=True,
        budget_reservation={**previous["budget_reservation"],
            "reserved_USD": 2.0, "previous_outstanding_reserved_USD": float(prior_reserved),
            "total_conservative_reservation_USD": float(prior_reserved + proposed),
            "reservation_created_by_preparation": False,
            "basis": "Proposal checked against bound complete accounting; no reserve creation, refund or actual cost claim."})
    return {**body, "plan_sha256": digest(body)}, raw


def _reprepare(plan):
    return prepare(plan["execution_output"], plan["environment_path"], **plan["budget_guard"]["inputs"])


def write_preparation(prepared, output):
    plan, raw = prepared
    if _reprepare(plan) != prepared:
        raise ValueError("Exact unchanged proposal and request bindings required")
    support, _, _ = old.controls.quote.base.old.v1.common.backend(plan["code_root"])
    target, run = support.transport._fresh(output), support.transport._fresh(plan["execution_output"])
    for a, b in ((target, old.PREVIOUS), (run, old.PREVIOUS), (target, run)):
        if a.is_relative_to(b) or b.is_relative_to(a):
            raise ValueError("Evidence directories must not overlap")
    target.mkdir()
    support._publish(target / "plan.json", plan)
    with (target / "request.json").open("xb") as stream:
        stream.write(raw)
    return {"status": "prepared_not_started", "model_calls": 0, "plan_sha256": plan["plan_sha256"],
            "budget_state_modified": False}


def verify(path):
    path = unlinked(path)
    plan = old.controls.quote.base.old.v1.common.strict_plan(path.read_bytes())
    if (plan.get("protocol") != PROTOCOL
            or plan.get("plan_sha256") != digest({k: v for k, v in plan.items() if k != "plan_sha256"})):
        raise ValueError("Exact sealed V2 diagnostic plan required")
    actual = plan, unlinked(path.parent / "request.json").read_bytes()
    if _reprepare(plan) != actual:
        raise ValueError("Bound financial gate, code, source or request changed")
    return actual


def execute(path, *, approved_plan_sha256, wire=azure_wire,
            clock=time.monotonic, epoch=time.time):
    plan, raw_request = verify(path)
    if approved_plan_sha256 != plan["plan_sha256"]:
        raise ValueError("Exact reviewed new plan required")
    previous_epoch = datetime.fromisoformat(plan["previous_dispatch_UTC"].replace("Z", "+00:00")).timestamp()
    if epoch() < previous_epoch + 60.001:
        raise ValueError("Previous rolling minute must settle before one diagnostic")
    support, _, Journal = old.controls.quote.base.old.v1.common.backend(plan["code_root"])
    config = old.controls.quote.base.old.v1.probe.load_config(plan["environment_path"])
    secrets, endpoints = old.environment_masks(plan["environment_path"], config)
    target = support.transport._fresh(plan["execution_output"])
    target.mkdir()
    support._publish(target / "frozen_plan.json", plan)
    with (target / "request.json").open("xb") as stream:
        stream.write(raw_request)
    start = clock()
    receipt = {"protocol": PROTOCOL, "plan_sha256": plan["plan_sha256"], "request_id": old.REQUEST_ID,
        "request_byte_sha256": sha256(raw_request).hexdigest(), "POST_attempts": 0, "http_status": None,
        "physical_dispatch_performed": False, "response_archive_complete": False,
        "unknown_execution": True, "metering_complete": False, "response_body_sha256": None,
        "raw_body_saved": False, "actual_cost_USD": None, "list_price_estimate_USD": None,
        "provider_runtime_seconds": None, "hardware_usage": None, "diagnostic_failure": None}
    journal = Journal(target / "ledger")
    with journal.locked():
        key = digest([plan["plan_sha256"], old.REQUEST_ID])
        journal.record("request_intent", key, request_byte_sha256=receipt["request_byte_sha256"], reserved_USD=2.0)
        try:
            receipt.update(dispatch_UTC=old.controls.quote.base.old.v1.probe._utc_timestamp())
            journal.record("dispatch", key, **receipt)
            payload = old.controls.quote.base.old.v1.common.strict_plan(raw_request)
            receipt.update(POST_attempts=1, physical_dispatch_performed=True)
            try:
                response = wire(config, payload, timeout=120)
                if type(response) not in (tuple, list) or len(response) not in (2, 3):
                    raise ValueError("Bounded response tuple required")
                status, raw = response[:2]
                complete = response[2] is True if len(response) == 3 else True
            except HTTPError as exc:
                status = exc.code
                raw, complete = _read_response(exc)
            receipt["http_status"] = status if type(status) is int else None
            receipt["HTTP_body_complete"] = complete
            accounting.book(receipt, raw, config, 4096, max_bytes=262144,
                strict_json=old.controls.quote.base.old.v1.probe._strict_json,
                price_estimate=old.controls.quote.base.old.v1.price_estimate)
            if not complete:
                receipt.update(unknown_execution=True, provider_completion_confirmed=False)
            latest = old.controls.quote.base.old.v1.probe.load_config(plan["environment_path"])
            latest_secrets, latest_endpoints = old.environment_masks(plan["environment_path"], latest)
            capture = diagnostics.capture_metadata(raw, secrets | latest_secrets, endpoints | latest_endpoints,
                                                   status=status, body_complete=complete)
            receipt["safe_error_codes"] = [row for row in capture["fields"] if row["path"].endswith(".code") and "value" in row]
            receipt.update(content_filter_finish_reported=capture["content_filter_finish_reported"],
                           filter_error_code_reported=capture["filter_error_code_reported"],
                           observed_finish_reasons=capture["observed_finish_reasons"])
            support._publish(target / "response_metadata.json", capture)
            if capture["raw_body_publishable"]:
                with (target / "response-body.json").open("xb") as stream:
                    stream.write(raw)
                receipt.update(raw_body_saved=True, response_archive_complete=True)
            if type(status) is not int or status != 200:
                receipt.update(diagnostics.safe_error(status, raw, secrets | latest_secrets,
                    endpoints | latest_endpoints, body_complete=complete))
            if not complete:
                receipt["diagnostic_failure"] = "HTTP_body_incomplete"
            elif capture["content_filter_finish_reported"]:
                receipt["diagnostic_failure"] = "filtered_completion_reported"
            elif type(status) is int and status == 200:
                _, details = old.controls.quote.base.provider_response(raw, config, 4096)
                receipt.update(details)
                if not receipt.get("provider_completion_confirmed"):
                    receipt["diagnostic_failure"] = "provider_completion_unconfirmed"
            verify(path)
            receipt["binding_verification_after"] = True
        except Exception:
            receipt["diagnostic_failure"] = "transport_capture_or_binding_unknown"
        accounting.finish_local(receipt)
        receipt.update(finish_UTC=old.controls.quote.base.old.v1.probe._utc_timestamp(),
            client_elapsed_seconds=max(0.0, clock() - start), client_time_is_not_provider_time=True,
            automatic_retries=0, judge_admitted=False, quality_measured=False, budget_state_modified=False)
        journal.record("request_terminal", key, **receipt)
        journal.record("run_terminal", plan["plan_sha256"], receipt_sha256=digest(receipt))
        receipt["ledger_terminal_sha256"] = digest(journal.events()[-1])
        support._publish(target / "receipt.json", receipt)
    return receipt


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group(required=True)
    for mode in ("prepare", "verify", "execute"):
        modes.add_argument("--" + mode, action="store_true")
    for name in ("run-output", "output", "plan", "proposal-path", "accounting-path", "release-path"):
        parser.add_argument("--" + name, type=Path)
    parser.add_argument("--resource-extension-path", type=Path, default=RESOURCE_EXTENSION)
    parser.add_argument("--env", type=Path, default=old.controls.quote.base.old.v1.probe.DEFAULT_ENV)
    parser.add_argument("--approved-plan-sha256")
    args = parser.parse_args(argv)
    try:
        if args.prepare:
            result = write_preparation(prepare(args.run_output, args.env,
                resource_extension_path=args.resource_extension_path, proposal_path=args.proposal_path,
                accounting_path=args.accounting_path, release_path=args.release_path), args.output)
        elif args.verify:
            result = {"verified": True, "model_calls": 0, "plan_sha256": verify(args.plan)[0]["plan_sha256"]}
        else:
            result = execute(args.plan, approved_plan_sha256=args.approved_plan_sha256)
    except Exception:
        result = {"protocol": PROTOCOL, "status": "local_guard_failure", "secret_or_error_body_published": False}
    print(canonical(result).decode())
    return int(result.get("status") == "local_guard_failure" or bool(result.get("diagnostic_failure")))


if __name__ == "__main__":
    raise SystemExit(main())
