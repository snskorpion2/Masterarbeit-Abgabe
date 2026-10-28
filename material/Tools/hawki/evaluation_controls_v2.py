"""HAWKI GPT-4.1 V2 diagnostics on the exact historical 30 KNOWN controls.

Preparation and verification are CPU-only. Execution needs the reviewed plan
seal, uses one immutable journal and never retries or repairs semantic content.
This changes provider AND format delivery, not only model quality. No human
gold, new holdout, judge admission, F1, native provider time or cost is created.
Historical V1 inputs remain unchanged. Fresh code revisions are explicitly bound.
"""
from __future__ import annotations

import argparse
from base64 import b64encode
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
from urllib.parse import unquote

HERE = Path(__file__).resolve()
MAIN_ROOT = HERE.parents[2]
TEST_PATH = MAIN_ROOT / "Tools/tests/test_hawki_evaluation_controls_v2.py"
spec = importlib.util.spec_from_file_location("hawki_control_transport_contract_v2", HERE.with_name("probe.py"))
probe = importlib.util.module_from_spec(spec)
spec.loader.exec_module(probe)
PROTOCOL = "hawki-known-source-controls:v2"
MODEL = "gpt-4.1"
REVISION = "archived-prompts-and-safe-response-accounting:r2"
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


def verify_frozen_controls(source_plan, code_root):
    """Audit historical inputs against current code without rewriting old seals.

    The old plan's byte-bound code dependencies may have advanced. This is a NEW
    reviewed condition, never a bypass or claim that the old plan verifies.
    Every non-code field, task, private label and original prompt must remain
    identical. Current dependency hashes are sealed by the new V2 plan.
    """
    support, original, _ = backend(code_root)
    path = unlinked(source_plan)
    old = strict_plan(path.read_bytes())
    if old.get("protocol") != original.PROTOCOL or old.get("plan_sha256") != support.inventory.digest(
            {k: v for k, v in old.items() if k != "plan_sha256"}):
        raise ValueError("Historical source plan seal is invalid")
    names = ("model_inputs/requests.json", "evaluator_private/assessment.json", "HUMAN_REVIEW_PACKET.json")
    actual = tuple(strict_plan(unlinked(path.parent / name).read_bytes()) for name in names)
    fresh, tasks, private, human = original.prepare(
        old["source_root"], budget_dir=old["evaluation_budget"]["directory"])
    ignored_revision_fields = {"code_sha256", "plan_sha256"}
    old_contract = {k: v for k, v in old.items() if k not in ignored_revision_fields}
    new_contract = {k: v for k, v in fresh.items() if k not in ignored_revision_fields}
    if old_contract != new_contract or actual != (tasks, private, human):
        raise ValueError("Historical sources, candidates, labels, metadata or original prompts changed")
    # Equality ignores dict insertion order. Only archived objects preserve
    # the exact candidate serialization used by the other frozen providers.
    return old, *actual


def dependency_revision(old, current):
    before = old["code_sha256"]
    changes = [{"path": name, "historical_sha256": before.get(name), "current_sha256": current.get(name)}
               for name in sorted(set(before) | set(current)) if before.get(name) != current.get(name)]
    return {"historical_plan_is_not_resealed": True,
            "new_reviewed_dependency_condition": bool(changes), "changed_code_bindings": changes}


def quote_backend(code_root):
    root = unlinked(code_root).resolve(strict=True)
    backend(root)
    worker = importlib.import_module("Experiments.triple_methods_v1.wse_source_controls_v1")
    expected = root / "Experiments/triple_methods_v1/wse_source_controls_v1.py"
    if Path(worker.__file__).resolve() != expected.resolve():
        raise ValueError("Quote validator resolved outside declared code root")
    return worker


def quote_payload(task, code_root):
    """Exactly the WSE/Kimi quote-only message contract, only transport differs."""
    request = quote_backend(code_root).request(task)
    return {"payload": {"model": MODEL, "messages": [
        {"role": item["role"], "content": {"text": item["content"]}}
        for item in request.messages]}}


def prepare(source_plan, code_root, run_output):
    support, original, _ = backend(code_root)
    source_plan = unlinked(source_plan)
    old, tasks, private, human = verify_frozen_controls(source_plan, code_root)
    if len(tasks) != 30 or Counter(task["axis"] for task in tasks) != {"EE": 10, "EV": 10, "VV": 10}:
        raise ValueError("The complete original 30-control inventory is required")
    for task in tasks:
        if set(task) != {"request_id", "axis", "source", "value"} or set(task["source"]) != {"text", "text_sha256"}:
            raise ValueError("Only the original source/candidate task fields are permitted")
    quotes = quote_backend(code_root)
    payloads = [hawki_payload(support.smoke_payload()), *[quote_payload(task, code_root) for task in tasks]]
    source_files = [binding(source_plan)] + [binding(source_plan.parent / name) for name in
                    ("model_inputs/requests.json", "evaluator_private/assessment.json", "HUMAN_REVIEW_PACKET.json")]
    own_code = [binding(path) for path in (HERE, HERE.with_name("probe.py"), TEST_PATH)]
    body = {"protocol": PROTOCOL, "revision": REVISION, "status": "prepared_not_started", "purpose": "evaluation_only",
            "source_plan": str(source_plan), "source_plan_sha256": old["plan_sha256"],
            "code_root": str(unlinked(code_root)), "execution_output": str(unlinked(run_output)),
            "host": probe.HOST, "route": probe.ROUTES["smoke"], "model": MODEL,
            "limits": deepcopy(LIMITS), "claim_guard": deepcopy(GUARDS),
            "source_files": source_files, "own_code_and_tests": own_code,
            "original_code_bindings": quotes.code_bindings(),
            "dependency_revision": dependency_revision(old, original.code_bindings()),
            "institutional_inference_costs_are_separate_and_unknown": True,
            "local_GPU_seconds_debited": None,
            "backend_context_token_cap": None, "backend_reasoning_token_cap": None,
            "public_tasks_sha256": digest(tasks), "private_review_sha256": digest(private),
            "human_review_packet_sha256": digest(human), "ordered_payloads_sha256": digest(payloads),
            "original_system_prompt_sha256": old["system_prompt_sha256"],
            "unit_contracts_sha256": old["unit_contracts_sha256"],
            "original_order_and_source_candidate_texts_preserved": True,
            "quote_evidence_instruction_changed": True, "quote_only_evidence_format": True,
            "quote_prompt_protocol": quotes.PROTOCOL,
            "quote_prompt_system_sha256": sha256(quotes.request(tasks[0]).messages[0]["content"].encode()).hexdigest(),
            "quote_messages_identical_to_WSE_controls": True,
            "format_only_prefix_sha256": sha256(FORMAT_PREFIX.encode()).hexdigest(),
            "format_message_sha256": [sha256(next(m["content"]["text"] for m in p["payload"]["messages"] if m["content"]["text"].startswith(FORMAT_PREFIX)).encode()).hexdigest() for p in payloads],
            "provider_and_format_condition_changed": True, "backend_schema_enforcement_verified": False,
            "provider_model_revision": None, "effective_sampling": None, "effective_reasoning": None,
            "provider_tokens": None, "provider_seconds": None, "cost_dollars": None,
            "client_time_is_not_provider_time": True,
            "source_quote_bridge": "Unique exact original quote to Unicode offsets; absent or ambiguous quotes stay invalid",
            "wrapper_bridge": deepcopy(WRAPPER),
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
            ("content-type", "date", "retry-after") and not _reflected(str(v), _capabilities(headers, token))}


def _capabilities(headers, token):
    values = {token}
    for name, value in headers.items():
        if not re.search(r"authorization|cookie|api.?key|token|secret", str(name), re.I):
            continue
        value = str(value)
        values.add(value)
        if str(name).lower() == "set-cookie":
            values.add(value.split(";", 1)[0].partition("=")[2].strip('"'))
        if value.lower().startswith("bearer "):
            values.add(value[7:].strip())
    return {value for value in values if value}


def _reflected(text, capabilities):
    views = (text, unquote(text), unquote(unquote(text)))
    return any(value in view or b64encode(value.encode()).decode() in view
               for value in capabilities for view in views)


def _private_pattern(text):
    return bool(re.search(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}|"
        r"\b[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}\b|/subscriptions/|/resourceGroups/|"
        r"(?:api[-_ ]?key|authorization|password|secret|token)\s*[:=]|"
        r"[A-Za-z]:\\(?:Users|Documents)|/(?:home|root|etc)/", text, re.I))


USAGE_FIELDS = ("prompt_tokens", "completion_tokens", "total_tokens", "input_tokens", "output_tokens", "reasoning_tokens", "cached_tokens")
STRUCTURE_FIELDS = frozenset("error errors innererror inner_error details code type param target status success content text message usage model finish_reason choices index prompt_tokens completion_tokens total_tokens input_tokens output_tokens reasoning_tokens cached_tokens completion_tokens_details prompt_tokens_details content_filter_result content_filter_results hate sexual violence self_harm jailbreak filtered detected severity".split())


def capture_response(raw, headers, token, support):
    """Capture safe diagnostics and primary counters BEFORE answer validation.

    Raw bytes are publishable only inside an explicit narrow JSON scope, after
    credential/cookie/private-data checks. Free error messages and tracebacks
    are never raw-published. Otherwise retain SHA and redacted field structure.
    """
    metadata = {"response_body_sha256": sha256(raw).hexdigest(), "response_body_bytes": len(raw),
        "strict_JSON": False, "raw_body_publishable": False, "fields": [], "safe_error_codes": [],
        "publication_guard_reasons": [], "credential_reflection": False,
        "captured_body_complete": len(raw) <= LIMITS["max_response_bytes"]}
    counts = {name: None for name in USAGE_FIELDS}
    if len(raw) > LIMITS["max_response_bytes"]:
        metadata["publication_guard_reasons"] = ["body_boundary_exceeded_hash_is_captured_bytes_only"]
        return None, metadata, counts
    try:
        value = support.strict_json(raw)
        if not isinstance(value, dict):
            raise ValueError("Object required")
        metadata["strict_JSON"] = True
        caps = _capabilities(headers, token)
        scan = raw.decode("utf-8") + "\n" + canonical(value).decode()
        reflected = _reflected(scan, caps)
        private = _private_pattern(scan)
        metadata["credential_reflection"] = reflected
        if reflected: metadata["publication_guard_reasons"].append("credential_or_header_capability_reflection")
        if private: metadata["publication_guard_reasons"].append("private_identifier_pattern")
        usage = value.get("usage") if isinstance(value.get("usage"), dict) else {}
        integer = lambda item: item if type(item) is int and item >= 0 else None
        counts = {name: integer(usage.get(name)) for name in USAGE_FIELDS}
        for name, container in (("reasoning_tokens", "completion_tokens_details"), ("cached_tokens", "prompt_tokens_details")):
            detail = usage.get(container)
            if counts[name] is None and isinstance(detail, dict): counts[name] = integer(detail.get(name))
        def walk(node, path="$", depth=0):
            if depth > 16 or len(metadata["fields"]) >= 128:
                raise ValueError("Structure boundary exceeded")
            if isinstance(node, dict):
                for key, child in node.items():
                    name = key if key in STRUCTURE_FIELDS else "field_sha256_" + sha256(key.encode()).hexdigest()[:16]
                    walk(child, path + "." + name, depth + 1)
            elif isinstance(node, list):
                for index, child in enumerate(node): walk(child, path + f"[{index}]", depth + 1)
            else:
                item = {"path": path, "type": type(node).__name__}
                if isinstance(node, str):
                    safe = not _reflected(node, caps) and not _private_pattern(node)
                    item["characters"] = len(node)
                    if safe: item["value_sha256"] = sha256(node.encode()).hexdigest()
                    if safe and path.endswith((".code", ".type")) and re.fullmatch(r"[A-Za-z_][A-Za-z0-9_.:-]{0,95}", node):
                        item["value"] = node
                    if safe and path.endswith(".code") and "value" in item:
                        metadata["safe_error_codes"].append({"path": path, "value": node})
                elif type(node) is bool or node is None: item["value"] = node
                elif type(node) is int and path.endswith(".status") and 100 <= node <= 599: item["value"] = node
                metadata["fields"].append(item)
        walk(value)
        # An error object is raw-safe only if it has machine fields, no prose.
        def machine_error(node):
            if not isinstance(node, dict) or not node: return False
            for key, child in node.items():
                if key in ("error", "innererror", "inner_error"):
                    if not machine_error(child): return False
                elif key in ("code", "type"):
                    if not isinstance(child, str) or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_.:-]{0,95}", child): return False
                elif key in ("param", "target"):
                    if child is not None: return False
                elif key == "status":
                    if type(child) is not int or not 100 <= child <= 599: return False
                elif key == "success":
                    if type(child) is not bool: return False
                else: return False
            return True
        success_scope = value.get("success") is True and set(value) <= {"success", "content", "usage", "model", "finish_reason"}
        content = value.get("content")
        success_scope = success_scope and (isinstance(content, str) or
            isinstance(content, dict) and set(content) == {"text"} and isinstance(content["text"], str))
        if "usage" in value:
            allowed_usage = set(USAGE_FIELDS) | {"completion_tokens_details", "prompt_tokens_details"}
            success_scope = success_scope and isinstance(value["usage"], dict) and set(value["usage"]) <= allowed_usage
            if isinstance(value["usage"], dict):
                for key, child in value["usage"].items():
                    if isinstance(child, dict):
                        success_scope = success_scope and set(child) <= {"reasoning_tokens", "cached_tokens"} and all(type(v) is int and v >= 0 for v in child.values())
                    else: success_scope = success_scope and type(child) is int and child >= 0
        for name in ("model", "finish_reason"):
            if name in value: success_scope = success_scope and isinstance(value[name], str) and bool(re.fullmatch(r"[A-Za-z0-9_.:-]{1,96}", value[name]))
        metadata["raw_body_publishable"] = bool(not reflected and not private and (success_scope or machine_error(value)))
        if not metadata["raw_body_publishable"] and not metadata["publication_guard_reasons"]:
            metadata["publication_guard_reasons"].append("outside_allowlisted_raw_JSON_scope")
        reported_model = value.get("model")
        metadata["reported_model"] = reported_model if isinstance(reported_model, str) and re.fullmatch(r"[A-Za-z0-9_.:-]{1,96}", reported_model) and not _reflected(reported_model, caps) and not _private_pattern(reported_model) else None
        reason = value.get("finish_reason")
        if reason is None and isinstance(value.get("choices"), list) and len(value["choices"]) == 1 and isinstance(value["choices"][0], dict):
            reason = value["choices"][0].get("finish_reason")
        metadata["reported_finish_reason"] = reason if reason in ("stop", "length", "content_filter", "tool_calls", "function_call") and not reflected else None
        return value, metadata, counts
    except (ValueError, TypeError, UnicodeError, RecursionError):
        metadata.update(raw_body_publishable=False, publication_guard_reasons=["strict_JSON_or_structure_invalid"], fields=[], safe_error_codes=[])
        return None, metadata, counts


def _store_response_body(target, ordinal, raw):
    path = target / "HTTP" / f"{ordinal:04d}-response-body.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as stream:
        stream.write(raw)
    return str(path.relative_to(target))


def usage_totals(receipts):
    physical = [row for row in receipts if row["physical_dispatch_performed"]]
    observed = {name: [row.get("provider_usage", {}).get(name) for row in physical] for name in USAGE_FIELDS}
    known = {name: [value for value in values if type(value) is int and value >= 0] for name, values in observed.items()}
    sums = {name: sum(values) if values else None for name, values in known.items()}
    complete = bool(physical) and all(row.get("metering_complete") is True for row in physical)
    return {"known_provider_tokens": sums, "provider_token_observations": {name: len(values) for name, values in known.items()},
            "provider_tokens": sums if complete else None, "metering_complete": complete}


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
    if _private_pattern(text):
        raise ValueError("Private response identifiers are not retained")
    return text


def execute(plan_path, env_path, *, approved_plan_sha256, wire=institutional_wire, clock=time.monotonic):
    plan, tasks, private, human, payloads = verify(plan_path)
    if approved_plan_sha256 != plan["plan_sha256"]:
        raise ValueError("Reviewed plan hash required before loading a token or making requests")
    support, original, Journal = backend(plan["code_root"])
    quotes = quote_backend(plan["code_root"])
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
                           "provider_usage": {name: None for name in USAGE_FIELDS}, "metering_complete": False,
                           "HTTP_response_received": False, "raw_body_saved": False,
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
                                   response_sha256=sha256(response.body).hexdigest(), response_bytes=len(response.body),
                                   HTTP_response_received=True)
                    envelope, capture, usage = capture_response(response.body, response.headers, token, support)
                    receipt.update(response_metadata=capture, provider_usage=usage, safe_error_codes=capture["safe_error_codes"],
                        provider_tokens=usage if any(v is not None for v in usage.values()) else None,
                        reported_model=capture.get("reported_model"), reported_finish_reason=capture.get("reported_finish_reason"))
                    primary = [usage[name] for name in ("prompt_tokens", "completion_tokens", "total_tokens")]
                    receipt["reported_usage_consistent"] = primary[2] == primary[0] + primary[1] if all(v is not None for v in primary) else None
                    receipt["metering_complete"] = receipt["reported_usage_consistent"] is True
                    if capture["raw_body_publishable"]:
                        try:
                            receipt["response_body_path"] = _store_response_body(target, ordinal, response.body)
                            receipt["raw_body_saved"] = True
                        except OSError:
                            receipt["error_category"] = failure = "response_body_storage_failure_after_HTTP"
                            break
                    if len(response.body) > LIMITS["max_response_bytes"]:
                        receipt["error_category"] = failure = "response_size_exceeded"
                        break
                    if response.status != 200:
                        receipt["error_category"] = failure = "HTTP_error_safe_capture_available"
                        break
                    if capture["credential_reflection"]:
                        receipt["error_category"] = failure = "response_capability_reflection_not_retained"
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
                        parsed = quotes.parse_quote(tasks[ordinal - 1], cleaned, confirmed=True)
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
                    try:
                        ledger.record("request_terminal", key, **receipt)
                    except OSError:
                        failure = "request_terminal_storage_failure_after_dispatch"
                        receipt["terminal_storage_failure"] = True
                        raise
            verify(plan_path)
            binding_after = True
        except BaseException as exc:
            failure = failure or "post_binding_or_runner_failure"
            ledger.record("run_failure", plan["plan_sha256"], exception_class=type(exc).__name__)
        complete = failure is None and smoke_ready(smoke) and len(observations) == 30 and binding_after
        assessment = original._assessment(tasks, private, observations, technically_complete=complete)
        totals = usage_totals(receipts)
        ledger.record("run_terminal", plan["plan_sha256"], complete=complete, failure=failure, **totals,
                      provider_seconds=None, cost_dollars=None, final_binding_verified=binding_after)
        summary = {"protocol": PROTOCOL, "plan_sha256": plan["plan_sha256"], "review_execution_complete": complete,
                   "failure": failure, "HTTP_requests": sum(r["physical_dispatch_performed"] for r in receipts),
                   "HTTP_receipts": len(receipts), "control_responses": len(observations),
                   "client_elapsed_seconds_through_assessment": max(0.0, clock() - started),
                   **totals, "provider_seconds": None, "cost_dollars": None,
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
