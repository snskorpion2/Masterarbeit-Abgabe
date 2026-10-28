"""Bounded, opt-in HAWKI diagnostics on the existing 30 KNOWN controls.

Preparation and verification are CPU-only. Execution needs the reviewed plan
seal, uses one immutable journal and never retries or repairs semantic content.
This changes provider AND format delivery, not only model quality. No human
gold, new holdout, judge admission, F1, native provider time or cost is created.
"""
from __future__ import annotations

import argparse
from collections import Counter
from copy import deepcopy
from dataclasses import dataclass
from hashlib import sha256
import importlib
import importlib.util
import json
from pathlib import Path
import re
import sys
import time
import urllib.error
import urllib.request

HERE = Path(__file__).resolve()
MAIN_ROOT = HERE.parents[2]
TEST_PATH = MAIN_ROOT / "Tools/tests/test_hawki_evaluation_controls.py"
spec = importlib.util.spec_from_file_location("hawki_control_transport_contract", HERE.with_name("probe.py"))
probe = importlib.util.module_from_spec(spec)
spec.loader.exec_module(probe)
PROTOCOL = "hawki-known-source-controls:v1"
MODEL = "gpt-5"
LIMITS = {"control_calls": 30, "source_free_smoke_calls": 1, "max_HTTP_requests": 31,
          "per_HTTP_timeout_seconds": 90, "dispatch_deadline_seconds": 1200,
          "max_response_bytes": probe.MAX_BYTES, "automatic_retries": 0,
          "backend_output_token_cap": None, "hard_total_wall_timeout": False}
FORMAT_PREFIX = "Output format contract only. This is not source evidence or a reference answer. Return one JSON object conforming exactly to this schema: "
WRAPPER = {"kind": "whole_json_markdown_fence_only", "content_changed": False,
           "schema_or_semantic_errors_repaired": False}
GUARDS = {"known_previously_used_AI_provisional_controls": True, "human_gold_created": False,
          "new_holdout": False, "independent_human_review_performed": False,
          "judge_admitted": False, "semantic_truth_verified": False, "P_R_F1": None,
          "system_MINE_score": None, "new_extraction": False,
          "isolated_model_effect_comparison": False, "automatic_cohort_dispatch": False}


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def digest(value):
    return sha256(canonical(value)).hexdigest()


def strict_plan(raw):
    def pairs(items):
        value = {}
        for key, item in items:
            if key in value:
                raise ValueError("Duplicate plan fields are not permitted")
            value[key] = item
        return value

    def invalid_constant(_):
        raise ValueError("Nonfinite plan values are not permitted")

    return json.loads(raw, object_pairs_hook=pairs, parse_constant=invalid_constant)


def smoke_ready(value):
    return isinstance(value, dict) and set(value) == {"ready"} and value["ready"] is True


def unlinked(path):
    path = Path(path).absolute()
    if any(p.is_symlink() or getattr(p, "is_junction", lambda: False)() for p in (path, *path.parents)):
        raise ValueError("Linked paths are not permitted")
    return path


def binding(path):
    path = unlinked(path)
    raw = path.read_bytes()
    return {"path": str(path), "file_sha256": sha256(raw).hexdigest(), "bytes": len(raw)}


def backend(code_root):
    root = unlinked(code_root).resolve(strict=True)
    expected = root / "Experiments/triple_methods_v1/semantic_support_local_v1.py"
    unlinked(expected).resolve(strict=True)
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    support = importlib.import_module("Experiments.triple_methods_v1.semantic_support_local_v1")
    original = importlib.import_module("Experiments.triple_methods_v1.abschluss_evaluation_gate_v1")
    journal = importlib.import_module("Experiments.triple_methods_v1.journal")
    if Path(support.__file__).resolve() != expected.resolve() or Path(original.CODE_ROOT).resolve() != root:
        raise ValueError("Validator package resolved outside its declared code root")
    return support, original, journal.Journal


def hawki_payload(old_payload):
    """Preserve both original message texts. Transfer grammar as format-only text."""
    originals = old_payload["messages"]
    schema = old_payload["format"]
    if not isinstance(schema, dict) or not isinstance(originals, list) or not originals:
        raise ValueError("Frozen messages and JSON schema required")
    messages = []
    for item in originals:
        if set(item) != {"role", "content"} or not isinstance(item["content"], str):
            raise ValueError("Only original plain-text message fields allowed")
        messages.append({"role": item["role"], "content": {"text": item["content"]}})
    format_message = {"role": "system", "content": {"text": FORMAT_PREFIX + canonical(schema).decode("utf-8")}}
    messages.insert(1 if messages[0]["role"] == "system" else 0, format_message)
    return {"payload": {"model": MODEL, "messages": messages}}


def unwrap_format(raw):
    if not isinstance(raw, str):
        return raw, []
    match = re.fullmatch(r"\s*```(?:json)?[ \t]*\r?\n(?P<inner>[\s\S]*?)\r?\n```\s*", raw)
    if match is None:
        return raw, []
    inner = match.group("inner")
    return inner, [{**WRAPPER, "raw_sha256": sha256(raw.encode()).hexdigest(), "inner_sha256": sha256(inner.encode()).hexdigest()}]


def prepare(source_plan, code_root, run_output):
    support, original, _ = backend(code_root)
    source_plan = unlinked(source_plan)
    old, tasks, private, human = original.verify(source_plan)
    if len(tasks) != 30 or Counter(task["axis"] for task in tasks) != {"EE": 10, "EV": 10, "VV": 10}:
        raise ValueError("The complete original 30-control inventory is required")
    for task in tasks:
        if set(task) != {"request_id", "axis", "source", "value"} or set(task["source"]) != {"text", "text_sha256"}:
            raise ValueError("Only the original source/candidate task fields are permitted")
    originals = [support.smoke_payload(), *[support.request_payload(task) for task in tasks]]
    payloads = [hawki_payload(value) for value in originals]
    source_files = [binding(source_plan)] + [binding(source_plan.parent / name) for name in
                    ("model_inputs/requests.json", "evaluator_private/assessment.json", "HUMAN_REVIEW_PACKET.json")]
    own_code = [binding(path) for path in (HERE, HERE.with_name("probe.py"), TEST_PATH)]
    body = {"protocol": PROTOCOL, "status": "prepared_not_started", "purpose": "evaluation_only",
            "source_plan": str(source_plan), "source_plan_sha256": old["plan_sha256"],
            "code_root": str(unlinked(code_root)), "execution_output": str(unlinked(run_output)),
            "host": probe.HOST, "route": probe.ROUTES["smoke"], "model": MODEL,
            "limits": deepcopy(LIMITS), "claim_guard": deepcopy(GUARDS),
            "source_files": source_files, "own_code_and_tests": own_code,
            "original_code_bindings": original.code_bindings(),
            "public_tasks_sha256": digest(tasks), "private_review_sha256": digest(private),
            "human_review_packet_sha256": digest(human), "ordered_payloads_sha256": digest(payloads),
            "original_system_prompt_sha256": old["system_prompt_sha256"],
            "unit_contracts_sha256": old["unit_contracts_sha256"],
            "original_order_and_message_texts_preserved": True,
            "format_only_prefix_sha256": sha256(FORMAT_PREFIX.encode()).hexdigest(),
            "format_message_sha256": [sha256(next(m["content"]["text"] for m in p["payload"]["messages"] if m["content"]["text"].startswith(FORMAT_PREFIX)).encode()).hexdigest() for p in payloads],
            "provider_and_format_condition_changed": True, "backend_schema_enforcement_verified": False,
            "provider_model_revision": None, "effective_sampling": None, "effective_reasoning": None,
            "provider_tokens": None, "provider_seconds": None, "cost_dollars": None,
            "client_time_is_not_provider_time": True,
            "source_quote_bridge": deepcopy(support.FORMAT_BRIDGE), "wrapper_bridge": deepcopy(WRAPPER),
            "in_flight_response_may_finish_after_dispatch_deadline": True,
            "reference_labels_never_in_model_payload": True, "control_count": 30}
    return {**body, "plan_sha256": digest(body)}, tasks, private, human, payloads


def write_preparation(prepared, output):
    plan, tasks, private, human, payloads = prepared
    if prepare(plan["source_plan"], plan["code_root"], plan["execution_output"]) != prepared:
        raise ValueError("Preparation changed before publication")
    support, _, _ = backend(plan["code_root"])
    target = support.transport._fresh(output)
    original_directory = Path(plan["source_plan"]).parent
    if target.is_relative_to(original_directory) or original_directory.is_relative_to(target):
        raise ValueError("Preparation must not overlap original control evidence")
    run_target = support.transport._fresh(plan["execution_output"])
    if run_target.is_relative_to(original_directory) or original_directory.is_relative_to(run_target):
        raise ValueError("Execution must not overlap original control evidence")
    if unlinked(plan["execution_output"]).is_relative_to(target) or target.is_relative_to(unlinked(plan["execution_output"])):
        raise ValueError("Preparation and execution must stay separate")
    target.mkdir()
    for name, value in (("plan.json", plan), ("model_inputs/requests.json", tasks),
                        ("model_inputs/wire_payloads.json", payloads), ("evaluator_private/assessment.json", private),
                        ("HUMAN_REVIEW_PACKET.json", human)):
        support._publish(target / name, value)
    return {"status": "prepared_not_started", "plan_sha256": plan["plan_sha256"], "model_calls": 0}


def verify(plan_path):
    plan_path = unlinked(plan_path)
    plan = strict_plan(plan_path.read_bytes())
    if plan.get("protocol") != PROTOCOL or plan.get("plan_sha256") != digest({k: v for k, v in plan.items() if k != "plan_sha256"}):
        raise ValueError("Exact reviewed HAWKI plan seal required")
    support, _, _ = backend(plan["code_root"])
    files = ("model_inputs/requests.json", "evaluator_private/assessment.json", "HUMAN_REVIEW_PACKET.json", "model_inputs/wire_payloads.json")
    actual = (plan, *[support.strict_json(unlinked(plan_path.parent / name).read_bytes()) for name in files])
    if prepare(plan["source_plan"], plan["code_root"], plan["execution_output"]) != actual:
        raise ValueError("Frozen source, candidates, prompt, schema, labels, code or tests changed")
    return actual


@dataclass(frozen=True)
class WireResponse:
    status: int
    body: bytes
    headers: dict


def institutional_wire(payload, *, token, timeout):
    req = urllib.request.Request(probe.HOST + probe.ROUTES["smoke"], data=canonical(payload), method="POST",
            headers={"Authorization": "Bearer " + token, "Accept": "application/json", "Content-Type": "application/json"})
    opener = urllib.request.build_opener(probe.NoRedirect())
    try:
        response = opener.open(req, timeout=timeout)
    except urllib.error.HTTPError as exc:
        response = exc
    with response:
        return WireResponse(response.code, response.read(LIMITS["max_response_bytes"] + 1), dict(response.headers.items()))


def _safe_headers(headers, token):
    return {str(k).lower(): str(v) for k, v in headers.items() if str(k).lower() in
            ("content-type", "date", "retry-after") and token not in str(v)}


def _success_text(body, token, support):
    value = support.strict_json(body)
    if not isinstance(value, dict) or value.get("success") is not True:
        raise ValueError("HAWKI did not confirm a successful response")
    if token in canonical(value).decode("utf-8"):
        raise ValueError("Credential reflection is not retained")
    content = value.get("content")
    text = content.get("text") if isinstance(content, dict) else content
    if not isinstance(text, str):
        raise ValueError("A plain success content string is required")
    if token in text:
        raise ValueError("Credential reflection is not retained")
    return text


def execute(plan_path, env_path, *, approved_plan_sha256, wire=institutional_wire, clock=time.monotonic):
    plan, tasks, private, human, payloads = verify(plan_path)
    if approved_plan_sha256 != plan["plan_sha256"]:
        raise ValueError("Reviewed plan hash required before loading a token or making requests")
    support, original, Journal = backend(plan["code_root"])
    token = probe.load_token(unlinked(env_path))
    target = support.transport._fresh(plan["execution_output"])
    target.mkdir()
    started = clock()
    deadline = started + LIMITS["dispatch_deadline_seconds"]
    observations, receipts = [], []
    failure, smoke, binding_after = None, None, False
    for name, value in (("frozen_plan.json", plan), ("model_inputs/requests.json", tasks),
                        ("evaluator_private/assessment.json", private), ("HUMAN_REVIEW_PACKET.json", human)):
        support._publish(target / name, value)
    ledger = Journal(target / "ledger")
    with ledger.locked():
        ledger.record("run_start", plan["plan_sha256"], protocol=PROTOCOL, limits=LIMITS, provider_tokens=None, provider_seconds=None, cost_dollars=None)
        try:
            for ordinal, payload in enumerate(payloads):
                remaining = deadline - clock()
                if remaining <= 0 or ordinal >= LIMITS["max_HTTP_requests"]:
                    failure = "dispatch_budget_exhausted"
                    break
                identifier = "source_free_smoke" if ordinal == 0 else tasks[ordinal - 1]["request_id"]
                key = digest([plan["plan_sha256"], identifier, ordinal])
                begin = clock()
                intent = {"ordinal": ordinal, "request_id": identifier, "request": payload, "request_sha256": digest(payload),
                          "monotonic_start": begin, "timeout_seconds": min(90, remaining)}
                ledger.record("request_start", key, **intent)
                receipt = {"ordinal": ordinal, "request_id": identifier, "physical_dispatch_performed": False,
                           "status": None, "headers": {}, "response_sha256": None, "raw_success_content": None,
                           "provider_tokens": None, "provider_seconds": None, "cost_dollars": None,
                           "semantic_judgment_available": False}
                try:
                    remaining = deadline - clock()
                    if remaining <= 0:
                        failure = "dispatch_budget_exhausted"
                        receipt["error_category"] = failure
                        break
                    receipt["physical_dispatch_performed"] = True
                    receipt["timeout_seconds"] = min(90, remaining)
                    response = wire(payload, token=token, timeout=receipt["timeout_seconds"])
                    if not isinstance(response, WireResponse) or type(response.status) is not int or not isinstance(response.body, bytes) or not isinstance(response.headers, dict):
                        raise ValueError("Raw HTTP status/body/header container required")
                    receipt.update(status=response.status, headers=_safe_headers(response.headers, token),
                                   response_sha256=sha256(response.body).hexdigest(), response_bytes=len(response.body))
                    if len(response.body) > LIMITS["max_response_bytes"]:
                        receipt["error_category"] = failure = "response_size_exceeded"
                        break
                    if response.status != 200:
                        receipt["error_category"] = failure = "HTTP_error_no_raw_error_body_saved"
                        break
                    raw = _success_text(response.body, token, support)
                    receipt["raw_success_content"] = raw
                    receipt["raw_success_content_sha256"] = sha256(raw.encode("utf-8")).hexdigest()
                    cleaned, bridges = unwrap_format(raw)
                    receipt["wrapper_bridges"] = bridges
                    if ordinal == 0:
                        smoke = support.strict_json(cleaned)
                        if not smoke_ready(smoke):
                            receipt["error_category"] = failure = "source_free_smoke_invalid"
                            break
                    else:
                        parsed = support.parse_response(tasks[ordinal - 1], cleaned, execution_confirmed=True)
                        parsed.update(provider_success_response_received=True, observation_status="HTTP_success_received",
                                      wrapper_bridges=bridges, raw_response=raw, status_and_reason_semantically_verified=False)
                        observations.append(parsed)
                        receipt["semantic_judgment_available"] = parsed["semantic_judgment_available"]
                except BaseException as exc:
                    # No exception string, stack trace, header, cookie or token is retained.
                    receipt["error_category"] = failure = "transport_or_response_unknown"
                    receipt["exception_class"] = type(exc).__name__
                    break
                finally:
                    receipt["client_HTTP_seconds"] = max(0.0, clock() - begin)
                    receipts.append(receipt)
                    ledger.record("request_terminal", key, **receipt)
            verify(plan_path)
            binding_after = True
        except BaseException as exc:
            failure = "post_binding_or_runner_failure"
            ledger.record("run_failure", plan["plan_sha256"], exception_class=type(exc).__name__)
        complete = failure is None and smoke_ready(smoke) and len(observations) == 30 and binding_after
        assessment = original._assessment(tasks, private, observations, technically_complete=complete)
        ledger.record("run_terminal", plan["plan_sha256"], complete=complete, failure=failure, provider_tokens=None,
                      provider_seconds=None, cost_dollars=None, final_binding_verified=binding_after)
        summary = {"protocol": PROTOCOL, "plan_sha256": plan["plan_sha256"], "review_execution_complete": complete,
                   "failure": failure, "HTTP_requests": sum(r["physical_dispatch_performed"] for r in receipts),
                   "HTTP_receipts": len(receipts), "control_responses": len(observations),
                   "client_elapsed_seconds_through_assessment": max(0.0, clock() - started),
                   "provider_tokens": None, "provider_seconds": None, "cost_dollars": None,
                   "provider_physical_generation_count": None, "provider_model_revision": None,
                   "backend_schema_enforcement_verified": False, "provider_and_format_condition_changed": True,
                   "judge_admitted": False, "P_R_F1": None, "system_MINE_score": None,
                   "binding_verification_after": binding_after, "assessment": assessment,
                   "ledger_terminal_sha256": digest(ledger.events()[-1]), "automatic_retries": 0}
        for name, value in (("responses.json", observations), ("HTTP_receipts.json", receipts), ("summary.json", summary)):
            support._publish(target / name, value)
    return summary


def main():
    parser = argparse.ArgumentParser()
    modes = parser.add_mutually_exclusive_group(required=True)
    for name in ("prepare", "verify", "execute"):
        modes.add_argument("--" + name, action="store_true")
    for name in ("source-plan", "code-root", "run-output", "output", "plan", "env"):
        parser.add_argument("--" + name, type=Path)
    parser.add_argument("--approved-plan-sha256")
    args = parser.parse_args()
    if args.prepare:
        if any(value is None for value in (args.source_plan, args.code_root, args.run_output, args.output)):
            parser.error("Preparation needs source plan, code root, run output and fresh output")
        result = write_preparation(prepare(args.source_plan, args.code_root, args.run_output), args.output)
    elif args.verify:
        result = {"verified": True, "plan_sha256": verify(args.plan)[0]["plan_sha256"], "model_calls": 0}
    else:
        if args.env is None:
            parser.error("Execution needs a local env file, never an inline token")
        result = execute(args.plan, args.env, approved_plan_sha256=args.approved_plan_sha256)
    print(canonical(result).decode("utf-8"))
    if args.execute and result["review_execution_complete"] is not True:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
