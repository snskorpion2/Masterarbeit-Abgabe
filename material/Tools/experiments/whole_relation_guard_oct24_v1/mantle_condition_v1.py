"""Model/transport adapter for the unchanged whole-statement guard.

The human-confirmed population is Gemini's 18 cases, not the separate 27-case
external-reviewer roster. One eligible statement per call retains full context.
No credentials or network activity occur at import, preparation, or scoring.
"""
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
import time
from uuid import uuid4

from Tools.experiments.fair_tail_oct23_v1 import runtime as mantle
from . import schema_delivery_v3 as schema

p = schema.p
PROTOCOL = "whole-relation-guard-mantle-single-statement:oct24-v1"
GEMINI_PIN = {"path": str(p.PRIVATE / "2026-10-24-whole-relation-guard-Gemini18-development-v1/Gemini-bound-manifest.private.json"),
              "bytes": 223567, "sha256": "8f0d4af50d845118eb64fda83bd2fd91f1ef625838683c7cc01302a0af9b54ec"}
GEMINI_TERMINAL = {"path": str(p.PRIVATE / "2026-10-24-whole-relation-guard-Gemini18-development-v1/actual/terminal.private.json"),
                   "bytes": 157338, "sha256": "3a5eccfe0c5f12032b4e89af31ee979d8989f33a7df427c95f371e696550fcc3"}
MODELS = ("deepseek.v3.2", "qwen.qwen3-32b")
OUTPUT_CAP, TIMEOUT, GAP = 8192, 300, 5
QUALIFICATION_FILE = p.ROOT / "Experiments/results/whole_relation_guard_mantle_oct24_v1/admission.json"


def source_cases():
    parent = p.checked(GEMINI_PIN, parse=True)
    p.need(len(parent["jobs"]) == 18, "Exact Gemini18 population required")
    for pin in parent["source_pins"] + parent["code_pins"]:
        p.checked(pin)
    p.need(sum(j["private_expected"].get("keep_expected") is True for j in parent["jobs"]) == 7
           and sum(j["private_expected"].get("keep_expected") is False for j in parent["jobs"]) == 8,
           "Frozen seven-positive/eight-negative population required")
    return parent


def delivered_packet(packet):
    """Deliver the existing v3 quote requirement for this eligible-ID subset."""
    packet = deepcopy(packet)
    incoming = p.contract.parse_json(packet["messages"][0]["content"])
    full = schema.schema_for({"case": {"source": {"text": incoming["source"]},
                                      "inventory": incoming["inventory"]}})
    selected = incoming["eligible_original_ids"]
    rows = full["properties"]["originals"]
    rows.update(minItems=len(selected), maxItems=len(selected))
    rows["items"]["properties"]["id"] = {"enum": selected}
    packet["schema"] = full
    return packet


def payload_for(packet, model):
    p.need(model in MODELS, "Only the two explicitly authorized model conditions")
    packet = delivered_packet(packet)
    system = packet["system"] + schema.MARKER + p.canonical(packet["schema"]).decode("utf8")
    return {"model": model, "temperature": 0, "max_tokens": OUTPUT_CAP,
            "stream": False, "n": 1,
            "messages": [{"role": "system", "content": system}, *packet["messages"]]}


def prepare(output, model):
    parent = source_cases()
    p.need(model in MODELS, "Authorized model required")
    output = Path(output).resolve()
    p.need(output.parent.is_dir() and not output.exists() and not output.is_relative_to(p.ROOT),
           "Fresh private output required; no replay")
    jobs = []
    for index, old in enumerate(parent["jobs"]):
        case = old["case"]
        for record in case["inventory"]:
            if record["category"] not in {"EE", "VV"}:
                continue
            packet = p.guard.build_request(case["source"]["text"], case["inventory"], [record["id"]])
            body = payload_for(packet, model)
            jobs.append({"id": "case-%02d-statement-%02d" % (index + 1, len(jobs) + 1),
                         "case_index": index, "eligible_ids": [record["id"]], "payload": body,
                         "provider_payload_sha256": p.digest(body)})
    p.need(len(jobs) == 21, "Exactly 21 statements across unchanged 18 cases required")
    reader, old_wire, policy = mantle.definitions(mantle.READER)
    modules = [p.guard, schema, p, mantle, reader, old_wire, policy, p.private,
               p.contract, p.formatting, schema.d.channels, p.guard.controller]
    paths = [Path(m.__file__) for m in modules] + [Path(__file__), Path(__file__).with_name("c1_guard.py"),
        Path(__file__).with_name("test_c1_guard.py"), Path(__file__).with_name("test_mantle_condition_v1.py")]
    output.mkdir(exist_ok=False)
    for job in jobs:
        job["request_pin"] = p.save(output / "requests" / (job["id"] + ".json"), job["payload"])
    plan = {"protocol": PROTOCOL, "model": model, "output": str(output), "jobs": jobs,
            "gemini_manifest": GEMINI_PIN, "gemini_terminal": GEMINI_TERMINAL,
            "cases": [{"id": j["id"], "case": deepcopy(j["case"]),
                       "private_expected": deepcopy(j["private_expected"])} for j in parent["jobs"]],
            "source_pins": [GEMINI_PIN, GEMINI_TERMINAL, *parent["source_pins"]],
            "code_pins": [p.pin(path) for path in dict.fromkeys(paths)],
            "maximum_physical_POSTs": 21, "retries": 0, "output_cap": OUTPUT_CAP,
            "minimum_start_gap_seconds": GAP, "timeout_seconds": TIMEOUT,
            "gate": {"positive_kept": 7, "negative_removed_minimum": 6,
                     "output_aborts": 0, "unknown_executions": 0,
                     "natural_pairs_and_partial_losses_in_gate": False},
            "schema_prompt_logic_unchanged": True, "full_inventory_context_preserved": True,
            "reasoning_parameter": "omitted; provider default unknown", "money_cost": None}
    plan["output_limit_basis"] = {
        "deepseek.v3.2": "https://docs.aws.amazon.com/bedrock/latest/userguide/model-card-deepseek-deepseek-v3-2.html",
        "qwen.qwen3-32b": "https://docs.aws.amazon.com/bedrock/latest/userguide/model-card-qwen-qwen3-32b.html",
        "documented_max_output_tokens": 8192,
        "note": "The old Foundry Speciale condition is a different model/endpoint. Source15 already has one record per case; grouping only subdivides the three natural pairs. No claim the old model itself was repaired."}
    return p.save(output / "manifest.json", plan)


def verify(plan_pin):
    plan = p.checked(plan_pin, parse=True)
    p.RuntimeScope(plan_pin, plan["jobs"][0]["provider_payload_sha256"],
                   protocol=PROTOCOL, expected_jobs=21).verify()
    parent = source_cases()
    p.need(plan["cases"] == [{"id": j["id"], "case": j["case"], "private_expected": j["private_expected"]}
                             for j in parent["jobs"]], "Original cases/expectations changed")
    for job in plan["jobs"]:
        case = plan["cases"][job["case_index"]]["case"]
        expected = payload_for(p.guard.build_request(case["source"]["text"], case["inventory"], job["eligible_ids"]), plan["model"])
        p.need(job["payload"] == expected == p.checked(job["request_pin"], parse=True)
               and p.digest(expected) == job["provider_payload_sha256"], "Frozen model request drift")
    return plan


def call_saved(body, folder, *, config=None, scope=None, wire_factory=None):
    """Reuse original HTTP recorder, SDK, archive and completed-channel decoder."""
    folder = Path(folder)
    reader, old, _ = mantle.definitions(mantle.READER)
    configuration = config or old.probe.Config(reader.URL, old.load_key(), "bedrock-mantle", False)
    p.need(configuration.url == reader.URL, "Exact Mantle Stockholm route required")
    request_pin = p.save(folder / "declared-wire.json", body)
    wire = (mantle.one_wire(reader, old, [{"request": request_pin}], folder)
            if wire_factory is None else wire_factory)
    client = None
    result = {"request_pin": request_pin, "status": "halted", "receipt": None, "parsed": None}
    try:
        client = p.private.SourceBoundClient(folder / "native", scope=scope, config=configuration,
            wire=wire, model=body["model"], expected_response_model=body["model"],
            thinking=None, timeout=TIMEOUT, max_physical_posts=1)
        client.phase = "whole_relation_guard"
        response = client.client.chat.completions.create(**deepcopy(body))
        p.need(response.choices[0].finish_reason == "stop", "Output abort cannot pass")
        receipt = client.receipts[-1]
        p.need(receipt.get("unknown_execution") is False and receipt.get("text_completion_confirmed") is True
               and receipt.get("response_archive_complete") is True and receipt.get("http_status") == 200,
               "Known complete original response required")
        raw_pin = p.pin(client.output / receipt["private_response_body_path"])
        envelope = p.contract.parse_json(p.checked(raw_pin))
        _, _, _, parsed, fences, bridge = schema.d.channels._split_private(envelope["choices"][0]["message"])
        packet = p.contract.parse_json(body["messages"][1]["content"])
        p.guard.validate_response(packet["source"], packet["inventory"], parsed, packet["eligible_original_ids"])
        schema.Draft202012Validator(p.contract.parse_json(body["messages"][0]["content"].split(schema.MARKER)[1])).validate(parsed)
        result.update(status="valid", parsed=parsed, raw_response_pin=raw_pin,
                      format_bridges=fences, channel_bridge=bridge,
                      reported_model=envelope["model"], provider_usage=envelope.get("usage"))
    except BaseException as error:
        result["error_class"] = type(error).__name__
    finally:
        if client is not None:
            if client.receipts:
                result["receipt"] = deepcopy(client.receipts[-1])
                result["provider_usage"] = deepcopy(client.receipts[-1].get("provider_usage"))
                result["receipt_pin"] = p.pin(client.output / "calls/0000/receipt.json")
                raw_path = result["receipt"].get("private_response_body_path")
                if raw_path and (client.output / raw_path).is_file():
                    result["raw_response_pin"] = p.pin(client.output / raw_path)
            client.client.close()
        result["wire_callback_entries"] = getattr(wire, "attempts", None)
        p.save(folder / "observation.json", result)
    return result


def summarize(cases, applications, *, complete, observations):
    positive, negative, natural, partial = [], [], [], []
    for job, application in zip(cases, applications, strict=True):
        expected, case = job["private_expected"], job["case"]
        assessed = application["complete"] is True
        kept = {r["id"] for r in application["inventory"]}
        if "keep_expected" in expected:
            row = {"case_id": case["id"], "assessed": assessed,
                   "kept": case["inventory"][0]["id"] in kept if assessed else None}
            (positive if expected["keep_expected"] else negative).append(row)
            if case["id"] in {"E01-C008", "E01-C027"}:
                partial.append({"case_id": case["id"], "assessed": assessed,
                                "whole_record_removed": not row["kept"] if assessed else None,
                                "known_supported_component_lost": not row["kept"] if assessed else None,
                                "basis": "fixed mixed-content development control; original local inventory has one record"})
        else:
            natural.append({"case_id": case["id"], "assessed": assessed,
                            "original_kept": expected["original_id"] in kept if assessed else None,
                            "correct_counterpart_kept": expected["direct_id"] in kept if assessed else None,
                            "original_removal_required": expected["original_removal_required"]})
    receipts = [o["receipt"] for o in observations if o.get("receipt") is not None]
    unknown = sum(r.get("unknown_execution") is not False for r in receipts)
    aborts = sum(r.get("finish_reason") == "length" for r in receipts)
    pk, nr = sum(r["kept"] is True for r in positive), sum(r["kept"] is False for r in negative)
    complete = complete and all(a["complete"] for a in applications)
    return {"positive_kept": pk, "positive_total": 7, "negative_removed": nr, "negative_total": 8,
            "positive_unassessed": sum(not r["assessed"] for r in positive),
            "negative_unassessed": sum(not r["assessed"] for r in negative),
            "all_18_cases_technically_complete": complete, "output_aborts": aborts,
            "unknown_executions": unknown, "gate_passed": complete and pk == 7 and nr >= 6 and aborts == unknown == 0,
            "natural_pairs_outside_gate": natural, "partial_meaning_losses_outside_gate": partial,
            "known_partial_meaning_losses": sum(r["known_supported_component_lost"] is True for r in partial),
            "known_partial_risks_unassessed": sum(not r["assessed"] for r in partial),
            "known_partial_risk_denominator": 2, "total_partial_loss_recall_claim": False}


def execute(plan_pin, *, config=None, wire_factory=None):
    plan = verify(plan_pin)
    actual = Path(plan["output"]) / "actual"
    p.need(not actual.exists(), "An existing condition is never replayed")
    p.save(actual / "start.json", {"plan_pin": plan_pin, "automatic_retry": False})
    observations, applications, parsed_by_case, last = [], [], {}, None
    for job in plan["jobs"]:
        while last is not None and (delay := GAP - (time.monotonic() - last)) > 0:
            time.sleep(min(delay, 1))
        verify(plan_pin)
        scope = p.RuntimeScope(plan_pin, job["provider_payload_sha256"], protocol=PROTOCOL, expected_jobs=21)
        last = time.monotonic()
        obs = call_saved(job["payload"], actual / job["id"], config=config, scope=scope, wire_factory=wire_factory)
        obs.update(id=job["id"], case_index=job["case_index"])
        observations.append(obs)
        print(json.dumps({"condition": plan["model"], "completed_calls": len(observations), "status": obs["status"]}), flush=True)
        if obs["status"] != "valid":
            break
        parsed_by_case.setdefault(job["case_index"], []).extend(obs["parsed"]["originals"])
    complete = len(observations) == 21 and all(o["status"] == "valid" for o in observations)
    for index, entry in enumerate(plan["cases"]):
        case = entry["case"]
        parsed = {"originals": parsed_by_case.get(index, [])}
        result = p.guard.apply_response(case["source"]["text"], case["inventory"], parsed)
        applications.append(result)
    complete = complete and all(a["complete"] for a in applications)
    summary = summarize(plan["cases"], applications, complete=complete, observations=observations)
    usages = [o.get("provider_usage") for o in observations]
    summary["known_HTTP200_stop_calls"] = sum(o.get("receipt", {}).get("text_completion_confirmed") is True for o in observations)
    known_totals = [u["total_tokens"] for u in usages if type(u) is dict and type(u.get("total_tokens")) is int]
    summary["provider_total_tokens_known_subtotal"] = sum(known_totals) if known_totals else None
    summary["all_usage_known"] = bool(usages) and len(known_totals) == len(usages)
    return p.save(actual / "terminal.json", {"protocol": PROTOCOL, "plan_pin": plan_pin,
        "model": plan["model"], "summary": summary, "observations": observations,
        "applications": applications, "unstarted_jobs": [j["id"] for j in plan["jobs"][len(observations):]],
        "human_gold": False, "fresh_transfer_or_pipeline_quality_claim": False, "money_cost": None})


def default_completion():
    """Two-argument C1 API uses only the explicitly qualified selected condition."""
    admission = json.loads(QUALIFICATION_FILE.read_text(encoding="utf8"))
    terminal = p.checked(admission["terminal_pin"], parse=True)
    p.need(admission["admitted"] is True and terminal["summary"]["gate_passed"] is True
           and admission["model"] == terminal["model"] in MODELS, "No qualified guard condition available")
    plan = verify(terminal["plan_pin"])
    output = p.PRIVATE / ("whole-relation-guard-C1-" + uuid4().hex)
    def complete(packet):
        body = payload_for(packet, admission["model"])
        folder = output / uuid4().hex
        # Existing DynamicRequestScope is the normal source-bound runtime hook.
        from Experiments.fair_comparison_oct23_v1.dynamic_request_scope import DynamicRequestScope
        declared = p.save(folder / "request.json", body)
        intent = p.save(folder / "intent.json", {"ordinal": 0, "phase": "whole_relation_guard",
            "status": "not_dispatched", "messages": body["messages"],
            "declared_wire_payload_sha256": p.digest(body), "prompt_sha256": p.digest(body["messages"])})
        bindings = {"plan_pin": terminal["plan_pin"], "source_pins": plan["source_pins"],
            "carrier_producer_pins": [declared], "renderer_code_pins": plan["code_pins"],
            "phase": "whole_relation_guard", "wire_parameters": {k: v for k, v in body.items() if k != "messages"}}
        scope = DynamicRequestScope(bindings, p.digest(bindings))
        scope.bind_current(0, intent, declared, p.digest(body))
        result = call_saved(body, folder / "recorded", scope=scope)
        p.need(result["status"] == "valid", "C1 guard technical failure; inspect private observation")
        return result["parsed"]
    return complete
