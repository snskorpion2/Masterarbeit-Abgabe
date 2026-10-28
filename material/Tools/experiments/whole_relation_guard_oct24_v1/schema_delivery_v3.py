"""Explicit facet-quote schema delivery; old responses and costs stay immutable."""
from copy import deepcopy
from pathlib import Path
from hashlib import sha256
import time
from jsonschema import Draft202012Validator, ValidationError
from . import delivery_v2 as d

p = d.p
PROTOCOL = "whole-relation-guard-facet-quote-schema-delivery:oct24-v3"
PARENT_MANIFEST_SHA = "52be0d527bb110c9525a79ea2dba23a501e75594f0a9c9c7d4b86e274e586577"
PARENT_TERMINAL_SHA = "c735b78eece4518f7c6ca8d0db642a6b9bd26dafeb5d30b0997d810dbe2872dc"
MARKER = "\n\nOUTPUT_JSON_SCHEMA:\n"


def old_schema(job):
    return p.contract.parse_json(job["payload"]["messages"][0]["content"].split(MARKER)[1])


def schema_for(job):
    schema = p.guard.build_request(job["case"]["source"]["text"], job["case"]["inventory"])["schema"]
    facets = schema["properties"]["originals"]["items"]["properties"]["facets"]["properties"]
    for name, original in list(facets.items()):
        uncertain, decisive = deepcopy(original), deepcopy(original)
        uncertain["properties"]["status"]["enum"] = ["undetermined"]
        decisive["properties"]["status"]["enum"] = ["supported", "contradicted", "unsupported"]
        uncertain["properties"]["evidence_quotes"]["minItems"] = 0
        decisive["properties"]["evidence_quotes"]["minItems"] = 1
        facets[name] = {"oneOf": [uncertain, decisive]}
    Draft202012Validator.check_schema(schema)
    return schema


def revised_job(original):
    job = deepcopy(original)
    system = original["payload"]["messages"][0]["content"]
    prefix, _ = system.split(MARKER)
    job["payload"]["messages"][0]["content"] = prefix + MARKER + p.canonical(schema_for(original)).decode()
    job.update(actual_id="schema-v3-" + job["id"], provider_payload_sha256=p.digest(job["payload"]))
    return job


def contract_matrix(jobs):
    checks = 0
    for job in jobs:
        source, inventory = job["case"]["source"]["text"], job["case"]["inventory"]
        validator = Draft202012Validator(schema_for(job))
        for facet in p.guard.FACETS:
            for status in p.guard.STATUSES:
                for quotes in ([], [source[:32]]):
                    rows = [{"id": r["id"], "facets": {f: {"reason": "CPU contract only.",
                        "status": "undetermined", "evidence_quotes": []} for f in p.guard.FACETS},
                        "remove_authorized": False, "preserves_supported_content": False} for r in inventory]
                    rows[0]["facets"][facet].update(status=status, evidence_quotes=quotes)
                    parsed, expected = {"originals": rows}, status == "undetermined" or bool(quotes)
                    p.need(validator.is_valid(parsed) is expected, "Facet status/quote schema matrix failed")
                    try:
                        p.guard.validate_response(source, inventory, parsed)
                        accepted = True
                    except (ValueError, ValidationError):
                        accepted = False
                    p.need(accepted is expected, "Unchanged host/schema contract matrix differs")
                    checks += 1
    return {"jobs": len(jobs), "facet_status_quote_checks": checks, "passed": True,
            "model_calls": 0, "semantic_quality_claimed": False}


def _parsed(observation):
    raw = p.checked(observation["raw_response_pin"])
    return d.channels._split_private(p.contract.parse_json(raw)["choices"][0]["message"])[3]


def _parent(manifest_pin, terminal_pin):
    p.need(manifest_pin["sha256"] == PARENT_MANIFEST_SHA and terminal_pin["sha256"] == PARENT_TERMINAL_SHA,
           "Exact stopped v2 pins required")
    previous, original, _ = d._verify(manifest_pin)
    terminal = p.checked(terminal_pin, parse=True)
    old = terminal["observations"]
    p.need(terminal["manifest_pin"] == manifest_pin and terminal["technically_complete"] is False
           and [(o["id"], o["status"]) for o in old] == [("job-01", "valid"), ("job-02", "valid"), ("job-03", "halted")]
           and terminal["unstarted_jobs"] == [j["id"] for j in original["jobs"][3:]], "Exact stopped three-attempt boundary required")
    actual = Path(previous["output"]) / "actual"
    p.need(not any((actual / j["id"]).exists() for j in original["jobs"][3:])
           and sorted(actual.rglob("receipt.json")) == sorted(Path(o["receipt_pin"]["path"]) for o in old[1:]),
           "Another previous attempt prohibits this fixed continuation")
    for index, observation in enumerate(old):
        job, parsed = original["jobs"][index], _parsed(observation)
        if index < 2:
            application, _ = d._decode(job, observation)
            Draft202012Validator(schema_for(job)).validate(parsed)
            p.need(application == observation["application"], "Compatible old application differs")
        else:
            Draft202012Validator(old_schema(job)).validate(parsed)
            empty = [(r["id"], f, v["status"]) for r in parsed["originals"] for f, v in r["facets"].items()
                     if v["status"] != "undetermined" and not v["evidence_quotes"]]
            p.need(empty == [(job["case"]["inventory"][0]["id"], "qualifications", "supported")], "Only exact known V03 facet failure authorized")
            try:
                d._decode(job, observation)
            except ValueError as error:
                p.need(str(error) == "Exact whole-source quotes required; decisive judgments need evidence", "Different historical failure")
            else:
                raise ValueError("Historical V03 must remain invalid")
            p.need(not Draft202012Validator(schema_for(job)).is_valid(parsed), "New schema must reject unchanged old V03")
    p.need(len({o["receipt_pin"]["path"] for o in old}) == 3, "Three unique historical cost references required")
    return previous, original, old


def prepare_v3(output, parent_manifest_pin, parent_terminal_pin):
    previous, original, old = _parent(parent_manifest_pin, parent_terminal_pin)
    output = p.probe._regular(output).resolve()
    forbidden = (p.ROOT, p.ROOT.parent / "Masterarbeit-triple-methods-v1", Path(previous["output"]), Path(original["output"]))
    p.need(output.parent.is_dir() and not output.exists() and all(not output.is_relative_to(f) and not f.is_relative_to(output)
           for f in forbidden), "Fresh disjoint private v3 output required")
    jobs = [revised_job(j) for j in original["jobs"][2:]]
    matrix = contract_matrix(original["jobs"])
    artifacts = [o[k] for o in old for k in ("receipt_pin", "raw_response_pin", "assistant_pin", "request_pin")]
    plan = {**deepcopy(previous), "protocol": PROTOCOL, "output": str(output), "jobs": jobs,
        "maximum_physical_POSTs": 16, "parent_manifest_pin": parent_manifest_pin, "parent_terminal_pin": parent_terminal_pin,
        "source_pins": [*previous["source_pins"], parent_manifest_pin, parent_terminal_pin, *artifacts],
        "code_pins": [*previous["code_pins"], p.pin(__file__), p.pin(Path(__file__).with_name("test_schema_delivery_v3.py"))],
        "contract_matrix": matrix, "mixed_delivery_condition": True, "old_cost_references": [o["receipt_pin"] for o in old],
        "authorized_previous_failed_case_reconstruction": "job-03 only; new schema payload and actual identity",
        "old_V03_admitted": False, "raw_answers_modified": False, "preparation_authorizes_execution": False}
    output.mkdir(exist_ok=False)
    return p.save(output / "manifest.private.json", plan)


def _verify(manifest_pin):
    plan = p.checked(manifest_pin, parse=True)
    p.RuntimeScope(manifest_pin, plan["jobs"][0]["provider_payload_sha256"], protocol=PROTOCOL, expected_jobs=16).verify()
    previous, original, old = _parent(plan["parent_manifest_pin"], plan["parent_terminal_pin"])
    p.need(plan["jobs"] == [revised_job(j) for j in original["jobs"][2:]]
           and plan["maximum_physical_POSTs"] == 16 and all(plan[k] == previous[k] for k in (
               "model", "expected_response_model", "HTTP_timeout_seconds", "SDK_max_retries", "minimum_start_gap_seconds", "local_deadline_seconds")),
           "Only authorized prompt-schema/body/actual-ID delta allowed")
    return plan, original, old


def execute_v3(manifest_pin, *, approved_manifest_sha256, config, wire=p.transport.azure_wire, clock=time.monotonic, sleep=time.sleep):
    p.need(manifest_pin["sha256"] == approved_manifest_sha256, "Exact approved v3 manifest required")
    plan, original, old = _verify(manifest_pin)
    p.need(contract_matrix(original["jobs"]) == plan["contract_matrix"], "Whole pre-dispatch matrix changed")
    actual = p.probe._regular(Path(plan["output"]) / "actual")
    p.need(not actual.exists(), "Existing v3 cannot resume or replay")
    actual.mkdir(exist_ok=False)
    p.save(actual / "execution-start.private.json", {"manifest_pin": manifest_pin, "mixed_delivery_condition": True})
    observations, started, last_start = [], clock(), None
    for job in plan["jobs"]:
        client, wire_calls = None, 0
        folder = actual / job["actual_id"]
        obs = {**{k: deepcopy(job[k]) for k in ("id", "actual_id", "source_id", "arm", "draw", "stage")}, "status": "halted"}
        def once(current_config, payload, *, timeout):
            nonlocal wire_calls, last_start
            _verify(manifest_pin)
            p.need(wire_calls == 0 and timeout == 300 and p.digest(payload) == job["provider_payload_sha256"]
                   and clock() - started < p.DEADLINE, "One exact authorized v3 body within deadline required")
            wire_calls, last_start = 1, clock()
            return wire(current_config, payload, timeout=timeout)
        try:
            while last_start is not None and (delay := p.MIN_START_GAP - (clock() - last_start)) > 0:
                p.need(clock() - started < p.DEADLINE, "Local dispatch deadline reached")
                sleep(min(delay, 1.0))
            _verify(manifest_pin)
            p.need(clock() - started < p.DEADLINE, "Local dispatch deadline reached")
            obs["request_pin"] = p.save(folder / "declared-wire.private.json", job["payload"])
            scope = p.RuntimeScope(manifest_pin, job["provider_payload_sha256"], protocol=PROTOCOL, expected_jobs=16)
            client = p.private.SourceBoundClient(folder / "native", scope=scope, config=config, wire=once,
                model=plan["model"], expected_response_model=plan["expected_response_model"], thinking=None, timeout=300, clock=clock, max_physical_posts=1)
            client.phase = "relation_guard"
            response = client.client.chat.completions.create(**deepcopy(job["payload"]))
            obs["assistant_pin"] = p.save(folder / "assistant-original.utf8", response.choices[0].message.content.encode("utf8"))
            obs.update(receipt=deepcopy(client.receipts[-1]), receipt_pin=p.pin(client.output / "calls/0000/receipt.json"),
                       raw_response_pin=p.pin(client.output / client.receipts[-1]["private_response_body_path"]))
            Draft202012Validator(schema_for(original["jobs"][int(job["id"][-2:]) - 1])).validate(_parsed(obs))
            obs["application"], obs["channel_delivery"] = d._decode(job, obs)
            obs["status"] = "valid"
        except BaseException as error:
            obs["error_class"] = type(error).__name__
            obs["application"] = p.guard.apply_response(job["case"]["source"]["text"], job["case"]["inventory"], technical_failure=True)
        finally:
            obs["wire_invocations"] = wire_calls
            if client is not None:
                if client.receipts:
                    obs.update(receipt=deepcopy(client.receipts[-1]), receipt_pin=p.pin(client.output / "calls/0000/receipt.json"))
                client.client.close()
            observations.append(obs)
            p.save(folder / "observation.private.json", obs)
        print(p.canonical({"job_id": job["actual_id"], "status": obs["status"], "count": len(observations)}).decode(), flush=True)
        if obs["status"] != "valid":
            break
    admitted = [*deepcopy(old[:2]), *observations]
    complete = len(admitted) == 18 and all(o["status"] == "valid" for o in admitted)
    costs = [*plan["old_cost_references"], *[o["receipt_pin"] for o in observations if "receipt_pin" in o]]
    p.need(len({r["path"] for r in costs}) == len(costs), "Cost references must name unique physical attempts")
    return p.save(actual / "terminal.private.json", {"protocol": PROTOCOL, "manifest_pin": manifest_pin,
        "execution_kind": "provider" if wire is p.transport.azure_wire else "cpu_fakewire", "observations": admitted,
        "technically_complete": complete, "gate": p.evaluate_gate(original, admitted) if complete else None,
        "cost_references": costs, "historical_invalid_V03_receipt": old[2]["receipt_pin"], "old_V03_admitted": False,
        "unstarted_jobs": [j["actual_id"] for j in plan["jobs"][len(observations):]], "mixed_delivery_condition": True,
        "old_compatible_decisions": 2, "old_cost_reference_count": 3, "historical_results_modified": False, "actual_money_cost": None})
