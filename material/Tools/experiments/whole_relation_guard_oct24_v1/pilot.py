"""Finite private development pilot over the existing one-POST recorder.

Preparation makes no calls. Execution needs an exact externally approved manifest;
unknown transport or invalid output stops all remaining jobs without replay.
"""
from copy import deepcopy
from hashlib import sha256
import inspect
from pathlib import Path
import time

from Experiments.fair_comparison_oct23_v1 import source_bound_private_policy as private
from Experiments.fair_comparison_oct23_v1.native_tail_worker import pin, checked
from Experiments.strict_autoschemakg import contract
from Tools.azure import probe, http_failure_probe_v2 as transport
from Tools.hawki import evaluation_controls as formatting
from . import guard, controls

ROOT = Path(__file__).resolve().parents[3]
PRIVATE = Path('withheld-artifact/2d2dfa477bded74ea97d')
EXPORT = PRIVATE / "2026-10-24-main12-SS65-selective-original-input-export-v1/selected65-original-source-support-inputs.blind.private.json"
EXPORT_SHA = "7e4969d254b4a0053e5ce9643a0115e7834905858b3e5a0fc98d29fa872bea04"
MODEL, PROTOCOL = "DeepSeek-V3.2-Speciale", "whole-relation-guard-development-pilot:oct24-v1"
NATURAL_PREFIXES = (
    "c-290c164c51dd0124316d16ff670324bf599bf6b3f51e243cbbc625c2be3fe378",
    "c-43912fd7d87156b49db33e06adbbaf0d751e94fc252bfe0f80d5b486abfd8b0a",
    "c-08e19f17412611c594f42a8e5354674adb381177aa3a8fdc4f2dba5ba5dc3a89")
MIN_START_GAP, DEADLINE = 60, 6 * 60 * 60
need, canonical = guard._require, transport.canonical


def digest(value):
    return sha256(canonical(value)).hexdigest()


def save(path, value):
    private.original._save(Path(path), value if type(value) is bytes else canonical(value))
    return pin(path)


def _natural(export):
    rows, cases = checked(export, parse=True), []
    for index, prefix in enumerate(NATURAL_PREFIXES):
        found = [row["case"] for row in rows if row["case"]["id"] == prefix]
        need(len(found) == 1, "Exactly one frozen exposed case required")
        original = deepcopy(found[0]["candidate"])
        need(original["category"] == "VV", "Whole original VV required")
        direct = deepcopy(original)
        direct["id"] = "WRG-N%03d" % (index + 1)
        if index == 0:
            direct["value"]["Head"], direct["value"]["Tail"] = (
                original["value"]["Tail"], original["value"]["Head"])
            direct["value"]["Relation"] = "because"
        elif index == 1:
            direct["value"]["Relation"] = "before"
        else:
            direct["value"]["Tail"] = "Edward D. Adams donated the vase."
        cases.append({"id": "natural-%02d" % (index + 1), "source": deepcopy(found[0]["source"]),
            "inventory": [original, direct], "private_expected": {
                "original_id": original["id"], "direct_id": direct["id"],
                "original_removal_required": index < 2}})
    return cases


def _job(case, index, model):
    incoming = controls.guard_inputs(case)
    source = incoming["source"]
    need(sha256(source["text"].encode("utf8")).hexdigest() == source["sha256"],
         "Complete source text hash differs")
    packet = guard.build_request(source["text"], incoming["inventory"])
    system = packet["system"] + "\n\nOUTPUT_JSON_SCHEMA:\n" + canonical(packet["schema"]).decode("utf8")
    payload = {"model": model, "temperature": 0, "max_tokens": 8192, "stream": False, "n": 1,
               "messages": [{"role": "system", "content": system}, *packet["messages"]]}
    need(len(canonical(payload)) <= private.diagnostics.MAX_BYTES, "Full request exceeds recorder bound")
    return {"id": "job-%02d" % (index + 1), "case": incoming,
            "private_expected": deepcopy(case["private_expected"]), "payload": payload,
            "provider_payload_sha256": digest(payload), "source_id": source["id"],
            "arm": "synthetic_development" if index < 15 else "exposed_natural_development",
            "draw": 0, "stage": "relation_guard"}


def prepare(output, *, export_path=EXPORT, approved_export_sha256=EXPORT_SHA,
            model=MODEL, expected_response_model=MODEL):
    """Freeze fifteen controls and three exposed-source pairs, never dispatch."""
    output = probe._regular(output).resolve()
    need(output.parent.is_dir() and not output.exists() and not output.is_relative_to(ROOT)
         and not output.is_relative_to(ROOT.parent / "Masterarbeit-triple-methods-v1"),
         "Fresh private output outside repositories required")
    export = pin(export_path)
    need(export["sha256"] == approved_export_sha256, "Approved original export differs")
    cases = controls.control_cases()
    need(len(cases) == 15 and sum(c["private_expected"]["keep_expected"] for c in cases) == 7,
         "Frozen seven positive/eight negative controls required")
    source_pins = [export] + [pin(controls.ROOT / p) for p in controls._PINS]
    modules = (guard, controls, private, private.original, private.diagnostics,
               private.original.accounting, probe, transport, formatting, contract,
               guard.controller, guard.scope_prefix, guard.evidence, private.worker,
               private.worker.baseline, private.original.shared, private.original.immutable_publish)
    code_paths = [__file__, Path(__file__).with_name("test_pilot.py"), inspect.getsourcefile(pin),
                  inspect.getsourcefile(guard.controller._native_value)]
    code_paths += [inspect.getsourcefile(m) for m in modules]
    jobs = [_job(case, i, model) for i, case in enumerate(cases + _natural(export))]
    plan = {"protocol": PROTOCOL, "output": str(output), "jobs": jobs,
            "source_pins": source_pins, "code_pins": [pin(p) for p in dict.fromkeys(code_paths)],
            "model": model, "expected_response_model": expected_response_model,
            "maximum_physical_POSTs": 18, "maximum_POSTs_per_job": 1,
            "HTTP_timeout_seconds": 300, "SDK_max_retries": 0,
            "minimum_start_gap_seconds": MIN_START_GAP, "local_deadline_seconds": DEADLINE,
            "human_gold": False, "fresh_natural_confirmation": False,
            "preparation_authorizes_execution": False, "response_repair": False}
    output.mkdir(exist_ok=False)
    return save(output / "manifest.private.json", plan)


class RuntimeScope:
    """Exact single body plus immutable manifest, helper and source pins."""
    def __init__(self, manifest_pin, body_sha256, *, protocol=PROTOCOL, expected_jobs=18):
        self.manifest_pin, self.body_sha256 = deepcopy(manifest_pin), body_sha256
        self.protocol, self.expected_jobs = protocol, expected_jobs
        self.verify()

    def verify(self):
        plan = checked(self.manifest_pin, parse=True)
        need(type(self.expected_jobs) is int and self.expected_jobs > 0
             and plan["protocol"] == self.protocol and len(plan["jobs"]) == self.expected_jobs
             and self.body_sha256 in [j["provider_payload_sha256"] for j in plan["jobs"]],
             "Frozen finite pilot/body required")
        for item in [*plan["source_pins"], *plan["code_pins"]]:
            checked(item)
        return plan

    def admits_request(self, value):
        self.verify()
        return digest(value) == self.body_sha256

    def certificate(self):
        plan = self.verify()
        return {"protocol": private.PROTOCOL, "original_plan": deepcopy(self.manifest_pin),
                "approved_request_roster_sha256": self.body_sha256, "authorized_physical_calls": 1,
                "source_pins": deepcopy(plan["source_pins"]), "raw_body_publishable": False,
                "private_processing_is_publication_permission": False}


def evaluate_gate(plan, observations):
    """Terminal-only finite agreement; never admission to Main or human gold."""
    need(len(observations) == 18 and all(o["status"] == "valid" for o in observations),
         "Only technically complete pilot has a semantic gate")
    positive_kept, negative_not_supported, negative_removed = 0, 0, 0
    natural_removed, direct_kept = 0, 0
    for job, observation in zip(plan["jobs"], observations, strict=True):
        result, expected = observation["application"], job["private_expected"]
        retained = {r["id"] for r in result["inventory"]}
        judged = {r["id"]: r for r in result["controller_judgments"]["originals"]}
        if "keep_expected" in expected:
            ident = job["case"]["inventory"][0]["id"]
            if expected["keep_expected"]:
                positive_kept += ident in retained
            else:
                negative_not_supported += judged[ident]["status"] != "supported"
                negative_removed += ident not in retained
        else:
            direct_kept += expected["direct_id"] in retained
            natural_removed += (expected["original_removal_required"]
                                and expected["original_id"] not in retained)
    return {"positive_kept": positive_kept, "negative_not_supported": negative_not_supported,
            "negative_removed": negative_removed, "natural_causal_removed": natural_removed,
            "natural_direct_kept": direct_kept,
            "passed": (positive_kept == 7 and negative_not_supported == 8 and negative_removed >= 6
                       and natural_removed == 2 and direct_kept == 3),
            "human_gold_or_general_judge_admission": False}


def execute(manifest_pin, *, approved_manifest_sha256, config, wire=transport.azure_wire,
            clock=time.monotonic, sleep=time.sleep):
    """One serial attempt per job. No retry, fallback, implicit resume or replay."""
    need(manifest_pin["sha256"] == approved_manifest_sha256, "Exact externally approved manifest required")
    plan = checked(manifest_pin, parse=True)
    scope = RuntimeScope(manifest_pin, plan["jobs"][0]["provider_payload_sha256"])
    actual = probe._regular(Path(plan["output"]) / "actual")
    need(not actual.exists(), "Existing actual evidence cannot be resumed/replayed")
    actual.mkdir(exist_ok=False)
    started, last_start, observations = clock(), None, []
    save(actual / "execution-start.private.json", {"manifest": manifest_pin,
         "execution_kind": "provider" if wire is transport.azure_wire else "cpu_fakewire",
         "endpoint_sha256": sha256(config.url.encode()).hexdigest(), "automatic_retries": 0})
    for job in plan["jobs"]:
        client, text, wire_calls = None, None, 0
        obs = {k: deepcopy(job[k]) for k in ("id", "source_id", "arm", "draw", "stage")}
        obs["status"] = "halted"
        folder = actual / job["id"]

        def once(current_config, payload, *, timeout):
            nonlocal wire_calls, last_start
            scope.verify()
            need(wire_calls == 0 and timeout == 300 and digest(payload) == job["provider_payload_sha256"]
                 and clock() - started < DEADLINE, "One exact request within local deadline required")
            wire_calls, last_start = 1, clock()
            return wire(current_config, payload, timeout=timeout)

        try:
            while last_start is not None and (delay := MIN_START_GAP - (clock() - last_start)) > 0:
                need(clock() - started < DEADLINE, "Local six-hour dispatch deadline reached")
                sleep(min(delay, 1.0))
            need(clock() - started < DEADLINE, "Local six-hour dispatch deadline reached")
            scope = RuntimeScope(manifest_pin, job["provider_payload_sha256"])
            need(digest(job["payload"]) == job["provider_payload_sha256"], "Frozen provider body changed")
            obs["request_pin"] = save(folder / "declared-wire.private.json", job["payload"])
            client = private.SourceBoundClient(folder / "native", scope=scope, config=config, wire=once,
                model=plan["model"], expected_response_model=plan["expected_response_model"],
                thinking=None, timeout=300, clock=clock, max_physical_posts=1)
            client.phase = "relation_guard"
            response = client.client.chat.completions.create(**deepcopy(job["payload"]))
            text = response.choices[0].message.content
            obs["assistant_pin"] = save(folder / "assistant-original.utf8", text.encode("utf8"))
            inner, obs["format_bridges"] = formatting.unwrap_format(text)
            parsed = contract.parse_json(inner)
            source, inventory = job["case"]["source"]["text"], job["case"]["inventory"]
            guard.validate_response(source, inventory, parsed)
            obs["application"] = guard.apply_response(source, inventory, parsed)
            receipt = client.receipts[-1]
            need(receipt.get("POST_attempts") == 1 and receipt.get("unknown_execution") is False
                 and receipt.get("text_completion_confirmed") is True and receipt.get("raw_body_saved") is True
                 and receipt.get("response_archive_complete") is True, "Original complete receipt/raw required")
            obs["status"] = "valid"
        except BaseException as error:
            obs["error_class"] = type(error).__name__
            obs["application"] = guard.apply_response(job["case"]["source"]["text"],
                job["case"]["inventory"], technical_failure=True)
        finally:
            obs["wire_invocations"] = wire_calls
            if client is not None:
                if client.receipts:
                    obs["receipt_pin"] = pin(client.output / "calls/0000/receipt.json")
                    obs["receipt"] = deepcopy(client.receipts[-1])
                    if client.receipts[-1].get("raw_body_saved"):
                        obs["raw_response_pin"] = pin(client.output / client.receipts[-1]["private_response_body_path"])
                client.client.close()
            observations.append(obs)
            save(folder / "observation.private.json", obs)
        print(canonical({"job_id": job["id"], "status": obs["status"], "count": len(observations)}).decode(), flush=True)
        if obs["status"] != "valid":
            break
    complete = len(observations) == 18 and all(o["status"] == "valid" for o in observations)
    return save(actual / "terminal.private.json", {"protocol": PROTOCOL, "manifest_pin": manifest_pin,
        "execution_kind": "provider" if wire is transport.azure_wire else "cpu_fakewire",
        "technically_complete": complete, "observations": observations,
        "gate": evaluate_gate(plan, observations) if complete else None,
        "unstarted_jobs": [j["id"] for j in plan["jobs"][len(observations):]],
        "actual_money_cost": None, "automatic_retry_or_replay": False,
        "wire_invocations_are_not_independent_POST_attestation": True})
