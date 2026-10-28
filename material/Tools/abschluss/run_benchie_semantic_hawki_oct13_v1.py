"""New source/gold-bound HAWKI semantic-matching worker, no automatic dispatch.

Prepare/verify are offline. Execute requires a fresh external one-shot
reservation, an explicit plan SHA and the independent owned-process supervisor.
No historical HAWKI V4 plan or Core-267 release check is modified or bypassed.
Controls are analytically constructed, not independent human calibration.
"""
from __future__ import annotations

import argparse
import copy
from dataclasses import dataclass
import hashlib
import http.client
import importlib.util
import json
from pathlib import Path
import socket
import ssl
import subprocess
import sys
import tempfile
import time
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[2]
CODE = ROOT.parent / "Masterarbeit-triple-methods-v1"
SEM = "Tools/abschluss/prepare_benchie_semantic_matching_oct13_v1.py"
SEM_SHA = "a3c8d05c2ba7a0d347c262b90e964fad1d531d5b64b22919310684c0181872b0"
SEM_PLAN_SHA = "0303c8199f6b58eb36d08cb7da9da530ee69587295e2799e6514de89462ba9d1"
OWN = "Tools/abschluss/benchie_own_ee_v1.py"
OWN_SHA = "616d12d21af6120f36376d885c47246eeecc58a2f2313b96908f71de0e6708fa"
HAWKI_HELPER = "Tools/hawki/evaluation_controls_v2.py"
HAWKI_HELPER_SHA = "e35a253f0b9648cf0c90fcfe13900925a5aea7ad9e3a992bf95b447b0383e79b"
PROBE = "Tools/hawki/probe.py"
PROBE_SHA = "b26967262c438dc8c0aca8b8e22589f4f0b9a9e42a9ef2335c9d9c822679d1f1"
WHOLE, DISPATCH, SETTLEMENT, HTTP_SECONDS, CALLS = 900, 750, 850, 90, 39
MAX_RESPONSE_BYTES = 1048576
SERIES = "benchie-semantic-institutional-series-v1"
REP = "benchie-semantic-institutional-repetition-v1"
RESULT = "benchie-semantic-institutional-result-v1"
RESERVATION = "benchie-semantic-institutional-reservation-v1"
HOST, ROUTE = "hawki2.htwk-leipzig.de", "/api/ai-req"
CORE_FILES = ("publication_stream_v1.py", "wse_job_supervisor_v2.py")


def load(name, path, expected):
    raw = Path(path).read_bytes()
    if hashlib.sha256(raw).hexdigest() != expected:
        raise ValueError("Physically bound executable source changed")
    spec = importlib.util.spec_from_file_location(name, path)
    value = importlib.util.module_from_spec(spec)
    sys.modules[name] = value
    exec(compile(raw, str(path), "exec"), value.__dict__)
    return value


def helpers():
    own = load("_semantic_worker_io", ROOT / OWN, OWN_SHA)
    sem = load("_semantic_worker_contract", ROOT / SEM, SEM_SHA)
    # Reuse only pure response/accounting/token-loading helpers. Never call
    # historical prepare/execute/backend/code-commit admission functions.
    own.read(ROOT / PROBE, PROBE_SHA)
    safe = load("_semantic_worker_safe_hawki", ROOT / HAWKI_HELPER, HAWKI_HELPER_SHA)
    return own, sem, safe


def relative(value):
    p = Path(value)
    if p.is_absolute() or p.anchor or ".." in p.parts or not p.parts or any(":" in x for x in p.parts):
        raise ValueError("Canonical relative path required")
    if p.as_posix() != value:
        raise ValueError("Canonical relative separator required")
    return p


def code_bindings(own):
    names = (Path(__file__).relative_to(ROOT).as_posix(),
        "Tools/tests/test_benchie_semantic_hawki_oct13_v1.py", OWN, SEM, HAWKI_HELPER, PROBE,
        "Tools/abschluss/prepare_benchie_empty_diagnostic_oct13_v1.py",
        "Tools/abschluss/run_benchie_ee_cost_pilot_v1.py")
    return {name: own.sha(own.read(ROOT / name)) for name in names}


def core_bindings(own):
    # Both actual runtime helpers import only the standard library. Freeze
    # today's exact bytes, not the historical V4/Core267 source condition.
    return {name: own.sha(own.read(CODE / "Experiments/triple_methods_v1" / name)) for name in CORE_FILES}


def core(name, bindings, own):
    if name not in CORE_FILES or name not in bindings:
        raise ValueError("Declared helper closure required")
    path = CODE / "Experiments/triple_methods_v1" / name
    own.read(path, bindings[name])
    return load("_semantic_worker_core_" + name.removesuffix(".py"), path, bindings[name])


def rep_values(series_sha, repetition):
    if type(repetition) is not int or repetition not in (1, 2, 3):
        raise ValueError("Explicit judge repetition 1/2/3 required")
    return {"protocol": REP, "series_sha256": series_sha, "judge_repetition": repetition,
        "status": "prepared_not_started", "whole_seconds": WHOLE, "dispatch_seconds": DISPATCH,
        "settlement_end_seconds": SETTLEMENT, "per_HTTP_seconds": HTTP_SECONDS,
        "max_HTTP_requests": CALLS, "control_requests": 18, "nonempty_inventory_requests": 21,
        "empty_inventory_observations_no_HTTP": 27, "automatic_retries": 0,
        "source_free_smoke_generations": 0, "new_external_reservation_required": True,
        "budget_reservation_created": False, "judge_admitted": False}


def task_files(own, sem, plan_path, expected):
    if expected != SEM_PLAN_SHA:
        raise ValueError("Unchanged 0303 frozen semantic preparation required")
    sem.verify(plan_path, expected)
    frozen = own.strict_json(own.read(plan_path, expected))
    data = {name: own.strict_json(own.read(Path(plan_path).parent / name, sha)) for name, sha in frozen["file_sha256"].items()}
    tasks = data["evaluator_inputs/controls.json"] + data["evaluator_inputs/inventories.json"]
    by_id = {t["task_id"]: t for t in tasks}
    rows = data["evaluator_inputs/requests.json"]
    if len(tasks) != 66 or len(by_id) != 66 or len(rows) != 66 or len({r["task_id"] for r in rows}) != 66:
        raise ValueError("Exact distinct fixed task inventory required")
    for index, row in enumerate(rows):
        if (row["payload"] != sem.hawki_payload(by_id[row["task_id"]])
                or row["phase"] != ("controls" if index < 18 else "fixed_inventory")
                or type(row["dispatch_required"]) is not bool
                or row["dispatch_required"] != (True if index < 18 else bool(by_id[row["task_id"]]["predictions"]))):
            raise ValueError("Original complete source/gold/payload/order differs")
    if sum(row["dispatch_required"] for row in rows) != CALLS:
        raise ValueError("39 physical requests required, no added smoke")
    return frozen, data


def prepare(semantic_plan, expected_semantic_sha, output):
    own, sem, _ = helpers()
    frozen, data = task_files(own, sem, semantic_plan, expected_semantic_sha)
    target = own.fresh_output(output)
    before_code, before_core = code_bindings(own), core_bindings(own)
    source_revision = subprocess.run(["git", "rev-parse", "HEAD"], cwd=CODE, capture_output=True,
        text=True, check=True, timeout=10).stdout.strip()
    if len(source_revision) != 40:
        raise ValueError("Current Core source revision metadata required")
    target.mkdir(parents=True, exist_ok=False)
    files = {}
    for name, sha in frozen["file_sha256"].items():
        relative(name)
        files[name] = own.write(target / name, own.read(Path(semantic_plan).parent / name, sha))
    input_bindings = {"original_semantic_plan": {"path": str(Path(semantic_plan).absolute()), "sha256": expected_semantic_sha},
                      **{name: copy.deepcopy(value) for name, value in frozen["input_bindings"].items()}}
    # Bind all underlying diagnostic preparation inputs too, not just its seal.
    diagnostic = input_bindings["source_only_selection"]
    diag = own.strict_json(own.read(diagnostic["path"], diagnostic["sha256"]))
    input_bindings.update({"diagnostic_" + key: value for key, value in diag["input_bindings"].items()})
    for binding in input_bindings.values():
        p = Path(binding["path"])
        own.read(p if p.is_absolute() else ROOT / p, binding["sha256"])
    series = {"protocol": SERIES, "status": "prepared_not_started", "model": "gpt-5",
        "preparation_root": str(target.absolute()),
        "host": "https://" + HOST, "route": ROUTE,
        "semantic_plan_sha256": expected_semantic_sha, "semantic_preparation_unchanged": True,
        "judge_repetitions": 3, "max_total_HTTP_requests": 117, "maximum_planned_wall_seconds": 2700,
        "same_fixed_inventory_sets": 48, "reference_clusters_per_constructor": 39,
        "source_free_smoke_generations": 0, "model_calls": 0, "metadata_HTTP_calls": 0,
        "budget_reservations_created": 0, "automatic_next_repetition": False,
        "automatic_retries": 0, "gold_evaluator_only": True, "new_constructor_calls": 0,
        "no_fact_repair_or_postgeneration": True, "judge_admitted": False,
        "human_annotation_created": False, "semantic_truth_verified": False,
        "all_controls_required_before_nonempty_inventory": True, "no_partial_primary_score": True,
        "native_provider_generation_count": None, "effective_reasoning": None,
        "effective_sampling": None, "backend_output_cap": None, "provider_model_revision": None,
        "provider_execution_cancellation_attested": False,
        "unknown_provider_execution_retains_reservation_no_refund_no_replay": True,
        "historical_linear_forecast_seconds": frozen["historical_client_time_linear_forecast_seconds"],
        "forecast_is_hypothesis_not_guarantee": True, "matrix_complexity_cost_unmeasured": True,
        "historical_V4_and_Core267_gates_not_used_or_modified": True,
        "core_source_revision_at_preparation": source_revision,
        "core_revision_metadata_not_full_worktree_or_runtime_attestation": True,
        "own_code_sha256": before_code, "core_code_sha256": before_core,
        "physical_runtime_helper_closure_sha256": own.sha(own.canonical(before_core)),
        "python_executable_sha256": own.sha(own.read(sys.executable)),
        "file_sha256": files, "input_bindings": input_bindings,
        "publication_limits": {"max_files": 512, "max_total_bytes": 32 * 1024 * 1024, "max_file_bytes": 4 * 1024 * 1024},
        "claim_limit": "Eight previously generated development sources; analytical controls are not independent judge accuracy. Strict source/gold equivalence is a new metric, not official BenchIE-FL or complete EE/EV/VV KGC."}
    series_sha = own.write(target / "series.json", own.json_bytes(series))
    plans = {f"r{j}": {"path": f"r{j}/plan.json",
             "sha256": own.write(target / f"r{j}/plan.json", own.json_bytes(rep_values(series_sha, j)))} for j in (1, 2, 3)}
    if before_code != code_bindings(own) or before_core != core_bindings(own):
        raise ValueError("Physical executable closure changed during preparation")
    task_files(own, sem, semantic_plan, expected_semantic_sha)
    receipt = {"protocol": SERIES, "status": "prepared_not_started", "series_sha256": series_sha,
               "repetitions": plans, "model_calls": 0, "metadata_HTTP_calls": 0,
               "budget_reservations_created": 0, "maximum_HTTP_proposed": 117, "judge_admitted": False}
    own.write(target / "preparation.json", own.json_bytes(receipt))
    return receipt


def verify(plan_path, expected):
    own, sem, safe = helpers()
    own.require_sha(expected)
    plan_path = own.safe_path(plan_path)
    plan = own.strict_json(own.read(plan_path, expected))
    series_root = plan_path.parent.parent
    series = own.strict_json(own.read(series_root / "series.json", plan["series_sha256"]))
    if (series.get("protocol") != SERIES or plan != rep_values(plan["series_sha256"], plan["judge_repetition"])
            or series.get("semantic_plan_sha256") != SEM_PLAN_SHA or series.get("model") != "gpt-5"
            or series.get("host") != "https://" + HOST or series.get("route") != ROUTE
            or series.get("preparation_root") != str(series_root.absolute())
            or series.get("judge_admitted") is not False or series.get("max_total_HTTP_requests") != 117
            or series.get("maximum_planned_wall_seconds") != 2700
            or series.get("source_free_smoke_generations") != 0):
        raise ValueError("New explicit immutable institutional condition required")
    if (code_bindings(own) != series["own_code_sha256"] or core_bindings(own) != series["core_code_sha256"]
            or own.sha(own.canonical(series["core_code_sha256"])) != series["physical_runtime_helper_closure_sha256"]
            or own.sha(own.read(sys.executable)) != series["python_executable_sha256"]):
        raise ValueError("Physically frozen executable/CPU helper closure differs")
    for binding in series["input_bindings"].values():
        p = Path(binding["path"])
        own.read(p if p.is_absolute() else ROOT / p, binding["sha256"])
    b = series["input_bindings"]["original_semantic_plan"]
    _, original = task_files(own, sem, b["path"], b["sha256"])
    data = {name: own.strict_json(own.read(series_root / relative(name), sha)) for name, sha in series["file_sha256"].items()}
    if data != original:
        raise ValueError("Fixed original source/gold/expected/payload bytes differ")
    return own, sem, safe, series, plan, data


@dataclass
class WireResponse:
    status: int
    body: bytes
    headers: dict
    complete: bool = True


class WireInterrupted(Exception):
    def __init__(self, *, raw=b"", status=None, headers=None):
        super().__init__("Institutional response not confirmed complete")
        self.raw, self.status, self.headers = raw, status, headers or {}


def institutional_wire(raw, *, token, timeout, clock=time.monotonic):
    """One POST, no redirect/proxy/retry; bound every read by one deadline."""
    if type(raw) is not bytes or type(token) is not str or not token or any(c in token for c in "\r\n"):
        raise ValueError("Exact request bytes and private token required")
    if type(timeout) not in (int, float) or not 0 < timeout <= HTTP_SECONDS:
        raise ValueError("Bounded institutional HTTP deadline required")
    began, chunks, status, headers = clock(), [], None, {}
    connection = http.client.HTTPSConnection(HOST, timeout=timeout, context=ssl.create_default_context())
    try:
        connection.request("POST", ROUTE, body=raw, headers={"Authorization": "Bearer " + token,
            "Content-Type": "application/json", "Accept": "application/json", "Connection": "close"})
        remaining = timeout - (clock() - began)
        if remaining <= 0:
            raise TimeoutError("Deadline before response headers")
        if connection.sock is not None:
            connection.sock.settimeout(remaining)
        owned_socket = connection.sock
        response = connection.getresponse()
        status, headers = response.status, dict(response.getheaders())
        length = 0
        while True:
            # Known length exhausted / HTTPResponse EOF: do not touch a socket
            # already closed by read1. Chunked EOF still requires its terminator.
            if response.length == 0 or response.fp is None:
                break
            remaining = timeout - (clock() - began)
            if remaining <= 0:
                raise TimeoutError("Deadline during response body")
            if owned_socket is not None:
                owned_socket.settimeout(remaining)
            block = response.read1(min(65536, MAX_RESPONSE_BYTES + 1 - length))
            if not block:
                if response.length not in (0, None):
                    raise EOFError("Truncated fixed-length response")
                break
            chunks.append(block)
            length += len(block)
            if length > MAX_RESPONSE_BYTES:
                raise ValueError("Response cap exceeded; partial raw retained")
        return WireResponse(status, b"".join(chunks), headers)
    except Exception as error:
        partial = getattr(error, "partial", b"")
        if type(partial) is bytes and partial:
            chunks.append(partial)
        raise WireInterrupted(raw=b"".join(chunks), status=status, headers=headers) from error
    finally:
        connection.close()


def control_admission(expected, observations):
    if len(expected) != 18 or len(observations) != 18:
        return {"passed": False, "control_count": len(observations), "independent_accuracy_proven": False}
    by_id = {r["task_id"]: r for r in observations}
    passed = len(by_id) == 18 and all(r["task_id"] in by_id
        and type(by_id[r["task_id"]].get("counts")) is dict
        and by_id[r["task_id"]]["counts"]["TP"] == r["expected_maximum_matching_count"]
        and by_id[r["task_id"]]["counts"]["TP_is_lower_bound_when_unclear"] is False for r in expected)
    return {"passed": passed, "control_count": len(observations),
            "independent_accuracy_proven": False, "judge_admitted": False,
            "scope": "Necessary analytical task-functional control expectations, not human calibration"}


def run_requests(plan, data, stage, own, sem, safe, wire, *, token, started, clock=time.monotonic,
                 cost_sink=None):
    """Injected wire allows complete CPU fixtures without API/model calls."""
    tasks = {t["task_id"]: t for t in data["evaluator_inputs/controls.json"] + data["evaluator_inputs/inventories.json"]}
    expected = data["evaluator_private/control_expected.json"]
    rows = data["evaluator_inputs/requests.json"]
    schedule = {r["task_id"]: r for r in data["evaluator_inputs/judge_schedule.json"] if r["judge_repetition"] == plan["judge_repetition"]}
    receipts, observations, failure, controls = [], [], None, {"passed": False}
    physical, unknown = 0, 0
    for index, row in enumerate(rows):
        if index == 18:
            controls = control_admission(expected, observations)
            if not controls["passed"]:
                failure = "analytical_control_gate_failed"
                break
        task = tasks[row["task_id"]]
        identity = schedule[task["task_id"]]
        if row["dispatch_required"] is False:
            empty = {"task_id": task["task_id"], "source_sha256": task["source"]["source_sha256"],
                     "prediction_verdicts": [], "pair_verdicts": []}
            observations.append({"task_id": task["task_id"], "request_id": identity["request_id"],
                "phase": row["phase"], "response": empty, "counts": sem.response_counts(task, empty),
                "deterministic_empty_no_HTTP": True, "confidence": None})
            continue
        ordinal = physical + 1
        raw_request = own.canonical(row["payload"])
        receipt = {"ordinal": ordinal, "task_id": task["task_id"], "request_id": identity["request_id"],
            "phase": row["phase"], "physical_dispatch_performed": False, "HTTP_response_complete": False,
            "provider_usage": {k: None for k in safe.USAGE_FIELDS}, "metering_complete": False,
            "provider_execution_after_client_end_unknown": False, "provider_native_generation_count": None,
            "provider_seconds": None, "money_cost": None, "status": None, "request_sha256": own.sha(raw_request)}
        soft_control_failure = None
        try:
            if physical >= plan["max_HTTP_requests"] or clock() - started >= plan["dispatch_seconds"]:
                failure = "dispatch_deadline_or_cap_before_POST"
                break
            own.write(stage / "requests" / f"{ordinal:03d}.wire.json", raw_request)
            own.write(stage / "requests" / f"{ordinal:03d}.intent.json", own.json_bytes(receipt))
            if clock() - started >= plan["dispatch_seconds"]:
                failure = "dispatch_deadline_during_persistence_no_POST"
                break
            begin = clock()
            timeout = min(plan["per_HTTP_seconds"], started + plan["settlement_end_seconds"] - begin)
            if timeout <= 0:
                failure = "settlement_deadline_before_POST"
                break
            if cost_sink is not None:
                cost_sink("dispatch_boundary", ordinal, {
                    "HTTP_requests_known_lower_bound": physical,
                    "current_attempt_generation_absence_not_yet_proven": True,
                    "current_attempt_terminal_confirmed": False,
                    "no_automatic_refund_or_replay": True,
                    **safe.usage_totals(receipts)})
            # Missing terminal after this persisted boundary is an unknown
            # possible dispatch, never a proven free/cancelled attempt.
            own.write(stage / "requests" / f"{ordinal:03d}.boundary.json", own.json_bytes({
                "ordinal": ordinal, "request_id": identity["request_id"], "request_sha256": own.sha(raw_request),
                "generation_absence_not_yet_proven": True, "terminal_received": False}))
            if clock() - started >= plan["dispatch_seconds"]:
                failure = "dispatch_deadline_after_boundary_no_POST"
                break
            physical += 1
            receipt["physical_dispatch_performed"] = True
            raw, status, headers, complete = b"", None, {}, False
            try:
                response = wire(raw_request, token=token, timeout=timeout)
                if (type(response) is not WireResponse or type(response.status) is not int
                        or type(response.body) is not bytes or type(response.headers) is not dict
                        or type(response.complete) is not bool):
                    raise ValueError("Exact bounded wire response required")
                raw, status, headers, complete = response.body, response.status, response.headers, response.complete
            except WireInterrupted as error:
                raw, status, headers = error.raw, error.status, error.headers
            except Exception as error:
                receipt["exception_class"] = type(error).__name__
            receipt.update(client_HTTP_seconds=max(0.0, clock() - begin), status=status,
                HTTP_response_complete=complete, response_sha256=own.sha(raw), response_bytes=len(raw),
                headers=safe._safe_headers(headers, token))
            _, capture, usage = safe.capture_response(raw, headers, token, SimpleNamespace(strict_json=own.strict_json))
            # Malformed JSON is still scanned for directly recognizable header
            # capabilities before assigning a fixed-cohort technical outcome.
            if safe._reflected(raw.decode("utf-8", errors="replace"), safe._capabilities(headers, token)):
                capture["credential_reflection"] = True
                capture["raw_body_publishable"] = False
            receipt.update(response_metadata=capture, provider_usage=usage)
            counts = [usage[k] for k in ("prompt_tokens", "completion_tokens", "total_tokens")]
            receipt["metering_complete"] = all(v is not None for v in counts) and counts[2] == counts[0] + counts[1]
            receipt["raw_body_publication_allowed"] = complete and capture["raw_body_publishable"]
            receipt["raw_body_private_file"] = f"responses/{ordinal:03d}.raw"
            if not complete:
                unknown += 1
                receipt["provider_execution_after_client_end_unknown"] = True
                failure = "HTTP_incomplete_provider_execution_unknown_no_replay"
            elif len(raw) > MAX_RESPONSE_BYTES:
                failure = "HTTP_response_cap_exceeded"
            elif status != 200:
                unknown += 1  # Institutional 4xx/5xx does not prove no upstream generation.
                receipt["provider_execution_after_client_end_unknown"] = True
                failure = "HTTP_error_complete_raw_retained"
            elif capture["credential_reflection"] or (not capture["raw_body_publishable"] and row["phase"] != "controls"):
                failure = "response_publication_scope_failed_private_raw_retained"
            if cost_sink is not None:
                cost_sink("response_boundary", ordinal, {"HTTP_requests_known_lower_bound": physical,
                    "current_attempt_terminal_confirmed": complete,
                    "provider_execution_after_client_end_unknown": receipt["provider_execution_after_client_end_unknown"],
                    "no_automatic_refund_or_replay": True,
                    **safe.usage_totals([*receipts, receipt])})
            # Capture usage before persistence and semantic validation so failed
            # answers/storage do not erase known physical cost lower bounds.
            own.write(stage / receipt["raw_body_private_file"], raw)
            if failure:
                break
            if not capture["raw_body_publishable"]:
                raise ValueError("Complete 200 control outside safe JSON scope; raw retained privately")
            text = safe._success_text(raw, token, SimpleNamespace(strict_json=own.strict_json))
            if capture.get("reported_model") not in (None, "gpt-5"):
                raise ValueError("Reported model differs from explicit institutional model")
            parsed = sem.parse_response(task, text)  # no fences/repair/new facts
            counted = sem.response_counts(task, parsed)
            observations.append({"task_id": task["task_id"], "request_id": identity["request_id"], "phase": row["phase"],
                "response": parsed, "counts": counted,
                "deterministic_empty_no_HTTP": False, "confidence": None})
            if row["phase"] == "controls":
                expected_row = [r for r in expected if r["task_id"] == task["task_id"]]
                if (len(expected_row) != 1 or counted["TP"] != expected_row[0]["expected_maximum_matching_count"]
                        or counted["TP_is_lower_bound_when_unclear"]):
                    soft_control_failure = "analytical_control_expected_relation_failed"
            if clock() - started >= plan["settlement_end_seconds"]:
                failure = "settlement_deadline_after_response_no_partial_score"
                break
        except Exception as error:
            receipt["exception_class"] = type(error).__name__
            if (row["phase"] == "controls" and receipt["HTTP_response_complete"] is True
                    and receipt["status"] == 200 and not isinstance(error, OSError)):
                # Known complete 200 controls remain a fixed 18-case cohort.
                # Invalid IDs/JSON/quotes are observations, never repaired.
                soft_control_failure = "technical_control_invalid_complete_HTTP200"
                observations.append({"task_id": task["task_id"], "request_id": identity["request_id"],
                    "phase": "controls", "response": None, "counts": None,
                    "technical_invalid": True, "exception_class": type(error).__name__, "confidence": None})
            else:
                failure = "technical_storage_or_response_invalid"
        finally:
            receipt["failure"] = failure or soft_control_failure
            receipts.append(receipt)
            try:
                own.write(stage / "receipts" / f"{ordinal:03d}.json", own.json_bytes(receipt))
            except OSError:
                failure = "receipt_storage_failed_costs_retained_in_memory"
        if failure:
            break
    complete = failure is None and len(observations) == 66 and physical == CALLS and unknown == 0
    all_resolved = complete and all(not row["counts"]["TP_is_lower_bound_when_unclear"] for row in observations)
    inventory = [r for r in observations if r["phase"] == "fixed_inventory"]
    aggregate = None
    if all_resolved:
        tp = sum(r["counts"]["TP"] for r in inventory)
        n = sum(r["counts"]["unique_prediction_count"] for r in inventory)
        g = sum(r["counts"]["reference_cluster_count"] for r in inventory)
        p, r = tp / n if n else 0.0, tp / g
        aggregate = {"TP": tp, "n_unique_predictions": n, "g_reference_clusters": g,
                     "P": p, "R": r, "F1": 2 * p * r / (p + r) if p + r else 0.0,
                     "conditional_diagnostic_only_not_admitted_primary": True}
    report = {"protocol": RESULT, "judge_repetition": plan["judge_repetition"], "failure": failure,
        "complete_fixed_review": complete, "all_semantic_outputs_resolved": all_resolved,
        "HTTP_requests": physical, "HTTP_receipts": len(receipts), "unknown_executions": unknown,
        "controls": controls, "observations": observations, "receipts": receipts,
        "whole_phase_seconds_before_publication": max(0.0, clock() - started),
        **safe.usage_totals(receipts), "provider_seconds": None, "provider_native_generation_count": None,
        "effective_reasoning": None, "backend_output_cap": None, "money_cost": None,
        "judge_admitted": False, "semantic_truth_verified": False, "human_calibration_performed": False,
        "primary_P_R_F1": None, "conditional_reference_diagnostic": aggregate,
        "no_partial_primary_score": True, "automatic_retry_or_replay": False,
        "unknown_provider_execution_may_continue_and_is_not_refunded": unknown > 0}
    return report


def admit_reservation(path, expected, plan_sha, plan, own):
    value = own.strict_json(own.read(path, own.require_sha(expected)))
    required = {"protocol": RESERVATION, "state": "reserved", "plan_sha256": plan_sha,
        "series_sha256": plan["series_sha256"], "judge_repetition": plan["judge_repetition"],
        "whole_seconds": WHOLE, "max_HTTP_requests": CALLS, "prior_HTTP_requests": 0, "budget_pool": "evaluation"}
    if (any(value.get(k) != v or type(value.get(k)) is not type(v) for k, v in required.items())
            or type(value.get("reservation_id")) is not str or not value["reservation_id"]
            or len(value["reservation_id"]) > 256):
        raise ValueError("New exact external evaluation reservation required")
    return value


def worker(plan_path, expected, output, env_path):
    own, sem, safe, series, plan, data = verify(plan_path, expected)
    output = Path(output)
    capsule = own.strict_json(own.read(output / "supervisor_start.json"))
    admission = own.strict_json(own.read(output / "admission.json"))
    reservation_path = admission["reservation_path"]
    reserved = admit_reservation(reservation_path, admission["reservation_sha256"], expected, plan, own)
    consumed = own.strict_json(own.read(str(reservation_path) + ".consumed.json", admission["consumed_marker_sha256"]))
    claim = own.strict_json(own.read(Path(plan_path).with_name("execution_claim.json"), admission["execution_claim_sha256"]))
    if (capsule.get("protocol") != "own-wse-job-hard-deadline-v2" or capsule.get("whole_job_seconds") != WHOLE
            or admission.get("plan_sha256") != expected or consumed.get("plan_sha256") != expected
            or consumed.get("output") != str(output.absolute())
            or claim != consumed
            or consumed.get("reservation_id_sha256") != own.sha(reserved["reservation_id"].encode())):
        raise ValueError("Owned supervisor, exact one-shot external reservation and output binding required")
    stage = Path(tempfile.mkdtemp(prefix="benchie-semantic-hawki-private-"))
    if stage.is_relative_to(ROOT) or output.is_relative_to(stage) or stage.is_relative_to(output):
        raise ValueError("Private result staging must be disjoint")
    own.write(output / "private_staging.json", own.json_bytes({"path": str(stage), "retained": True,
        "plan_sha256": expected, "credential_not_written": True}))
    token = safe.probe.load_token(own.safe_path(env_path))
    started = capsule["started_monotonic_seconds"]
    def cost_sink(phase, ordinal, snapshot):
        own.write(output / "cost_capsules" / f"{ordinal:03d}-{phase}.json", own.json_bytes({
            "plan_sha256": expected, "reservation_id_sha256": admission["reservation_id_sha256"],
            "phase": phase, "ordinal": ordinal, "provider_seconds": None, "money_cost": None, **snapshot}))
    report = run_requests(plan, data, stage, own, sem, safe, institutional_wire,
                          token=token, started=started, cost_sink=cost_sink)
    report.update(plan_sha256=expected, series_sha256=plan["series_sha256"],
                  reservation_id_sha256=admission["reservation_id_sha256"])
    # Independent safe cost capsule exists even if raw publication is refused.
    cost = {k: report[k] for k in ("protocol", "plan_sha256", "series_sha256", "judge_repetition",
        "HTTP_requests", "unknown_executions", "known_provider_tokens", "provider_token_observations",
        "provider_tokens", "metering_complete", "provider_seconds", "money_cost", "reservation_id_sha256")}
    cost["unknown_no_automatic_refund"] = report["unknown_executions"] > 0
    own.write(output / "cost_capsule.json", own.json_bytes(cost))
    summary = {k: v for k, v in report.items() if k not in ("receipts", "observations")}
    summary_sha = own.write(stage / "summary.json", own.json_bytes(summary))
    own.write(stage / "observations.json", own.json_bytes(report["observations"]))
    own.write(stage / "HTTP_receipts.json", own.json_bytes(report["receipts"]))
    verify(plan_path, expected)
    if time.monotonic() - started >= SETTLEMENT:
        own.write(output / "failed_terminal.json", own.json_bytes({"plan_sha256": expected,
            "failure": "publication_time_budget_exhausted", "primary_score": None, "private_stage_retained": True}))
        return 2
    publisher = core("publication_stream_v1.py", series["core_code_sha256"], own)
    candidates = [p for p in stage.rglob("*") if p.is_file() and p.suffix != ".raw"]
    candidates += [stage / r["raw_body_private_file"] for r in report["receipts"] if r.get("raw_body_publication_allowed")]
    capabilities = {token}
    # Header-derived capabilities are already excluded by narrow response
    # capture; token's two JSON-escape layers are also scanned by Core publisher.
    try:
        published = publisher.publish_files(stage, output / "run", sorted(candidates), archive_root=output,
            forbidden_values=capabilities, limits=publisher.PublicationLimits(**series["publication_limits"]))
    except Exception as error:
        own.write(output / "failed_terminal.json", own.json_bytes({"plan_sha256": expected,
            "failure": "publication_failed_private_stage_retained", "exception_class": type(error).__name__,
            "primary_score": None, "all_physical_costs_remain_counted": True}))
        return 2
    pub_sha = own.write(output / "publication.json", own.json_bytes({"complete": True, "plan_sha256": expected,
        "publication": published, "private_stage_retained": True, "raw_private_unpublishable_count":
        sum(not r.get("raw_body_publication_allowed", False) for r in report["receipts"] if r["physical_dispatch_performed"])}))
    own.write(output / "completion.json", own.json_bytes({"protocol": RESULT, "plan_sha256": expected,
        "series_sha256": plan["series_sha256"], "judge_repetition": plan["judge_repetition"],
        "publication_complete": True, "publication_sha256": pub_sha, "summary_sha256": summary_sha,
        "complete_fixed_review": report["complete_fixed_review"], "all_semantic_outputs_resolved": report["all_semantic_outputs_resolved"],
        "HTTP_requests": report["HTTP_requests"], "unknown_executions": report["unknown_executions"],
        "reservation_id_sha256": admission["reservation_id_sha256"], "judge_admitted": False,
        "primary_P_R_F1": None, "automatic_next_repetition": False}))
    return 0 if report["complete_fixed_review"] and report["all_semantic_outputs_resolved"] else 2


def execute(plan_path, expected, reservation_path, expected_reservation_sha, env_path, output):
    own, _, _, series, plan, _ = verify(plan_path, expected)
    reserved = admit_reservation(reservation_path, expected_reservation_sha, expected, plan, own)
    output = own.fresh_output(output)
    if (output.is_relative_to(Path(plan_path).parent.parent) or Path(plan_path).parent.parent.is_relative_to(output)
            or own.safe_path(env_path).is_relative_to(output)):
        raise ValueError("Output, frozen input and private environment must be disjoint")
    marker = Path(str(reservation_path) + ".consumed.json")
    consumed = {"plan_sha256": expected, "series_sha256": plan["series_sha256"],
        "reservation_sha256": expected_reservation_sha, "reservation_id_sha256": own.sha(reserved["reservation_id"].encode()),
        "output": str(output.absolute()), "no_reset_no_replay_no_automatic_refund": True}
    # The plan-root claim prevents copying the same reservation to a second
    # pathname, and the preparation_root binding prevents cloned-plan replay.
    claim_sha = own.write(Path(plan_path).with_name("execution_claim.json"), own.json_bytes(consumed))
    marker_sha = own.write(marker, own.json_bytes(consumed))  # exclusive before credentials/bootstrap/HTTP
    output.mkdir(parents=True, exist_ok=False)
    own.write(output / "admission.json", own.json_bytes({**consumed, "reservation_path": str(Path(reservation_path).absolute()),
        "consumed_marker_sha256": marker_sha, "execution_claim_sha256": claim_sha}))
    supervisor = core("wse_job_supervisor_v2.py", series["core_code_sha256"], own)
    child = "import runpy,sys\nm=runpy.run_path(sys.argv[1]);sys.exit(m['worker'](sys.argv[2],sys.argv[3],sys.argv[4],sys.argv[5]))\n"
    outcome = supervisor.supervise_job(child, [str(Path(__file__).absolute()), str(Path(plan_path).absolute()), expected,
        str(output.absolute()), str(Path(env_path).absolute())], results_root=output, timeout_seconds=WHOLE)
    return {"output": str(output), "supervisor": outcome, "primary_P_R_F1": None,
            "automatic_next_repetition": False, "provider_cancellation_attested": False}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    mode = p.add_mutually_exclusive_group(required=True)
    for name in ("prepare", "verify", "execute"):
        mode.add_argument("--" + name, action="store_true")
    for name in ("semantic-plan", "plan", "reservation", "env", "output"):
        p.add_argument("--" + name, type=Path)
    for name in ("semantic-plan", "plan", "reservation"):
        p.add_argument("--expected-" + name + "-sha256")
    a = p.parse_args()
    if a.prepare:
        if not all((a.semantic_plan, a.expected_semantic_plan_sha256, a.output)):
            p.error("prepare requires frozen semantic plan/SHA and fresh output")
        result = prepare(a.semantic_plan, a.expected_semantic_plan_sha256, a.output)
    else:
        if not a.plan or not a.expected_plan_sha256:
            p.error("exact repetition plan/SHA required")
        if a.verify:
            _, _, _, _, plan, _ = verify(a.plan, a.expected_plan_sha256)
            result = {"verified": True, "status": "prepared_not_started", "model_calls": 0,
                      "max_HTTP_requests": plan["max_HTTP_requests"], "judge_admitted": False}
        else:
            if not all((a.reservation, a.expected_reservation_sha256, a.env, a.output)):
                p.error("execute requires new external reservation/SHA, private env and fresh output")
            result = execute(a.plan, a.expected_plan_sha256, a.reservation, a.expected_reservation_sha256, a.env, a.output)
    print(json.dumps(result, sort_keys=True, allow_nan=False))


if __name__ == "__main__":
    main()
