"""Opt-in existing Speciale channel delivery; immutable v1, exact unstarted suffix.

Recovered output is a derived read-only view, never a fresh request or booking.
"""
from copy import deepcopy
from pathlib import Path
from hashlib import sha256
import time

from Tools.azure import deepseek_speciale_channel_adapter_oct13_v1 as channels
from . import pilot as p

PROTOCOL = "whole-relation-guard-existing-channel-delivery:oct24-v2"
PARENT_MANIFEST_SHA = "0632a55b037bc6fa554bb1e49bef63705c124a4941a7e78f7b79498b5307bed8"
PARENT_TERMINAL_SHA = "8f23134a3af74beddbc9befd0523fa596d8102f523424486780ddfaf9c0e69f9"


def _decode(job, observation):
    receipt = p.checked(observation["receipt_pin"], parse=True)
    raw = p.checked(observation["raw_response_pin"])
    request = p.checked(observation["request_pin"], parse=True)
    assistant = p.checked(observation["assistant_pin"])
    p.need(receipt == observation["receipt"] and request == job["payload"]
           and receipt["wire_sha256"] == job["provider_payload_sha256"] == p.digest(request)
           and receipt["response_sha256"] == sha256(raw).hexdigest()
           and receipt["response_bytes"] == len(raw), "Original provider artifact mismatch")
    expected = {"POST_attempts": 1, "unknown_execution": False, "http_status": 200,
        "finish_reason": "stop", "HTTP_body_complete": True, "text_completion_confirmed": True,
        "raw_body_saved": True, "response_archive_complete": True, "error_class": None}
    p.need(all(receipt.get(k) == v and type(receipt.get(k)) is type(v) for k, v in expected.items()),
           "One known completed archived original response required")
    envelope = p.contract.parse_json(raw)
    p.need(len(envelope["choices"]) == 1 and envelope["choices"][0]["finish_reason"] == "stop"
           and envelope["model"] == receipt["expected_response_model"], "Original provider completion differs")
    message = envelope["choices"][0]["message"]
    p.need(message["content"].encode("utf8") == assistant, "Assistant/provider content mismatch")
    thinking, final, clean, parsed, fences, bridge = channels._split_private(message)
    source, inventory = job["case"]["source"]["text"], job["case"]["inventory"]
    p.guard.validate_response(source, inventory, parsed)
    application = p.guard.apply_response(source, inventory, parsed)
    p.need(application["complete"] is True, "Unchanged whole guard application failed")
    return application, {"adapter_protocol": channels.PROTOCOL, "bridge": bridge,
        "format_bridges": fences, "final_sha256": sha256(final.encode("utf8")).hexdigest(),
        "clean_json_sha256": sha256(clean.encode("utf8")).hexdigest(),
        "reasoning_characters": None if thinking is None else len(thinking)}


def _parent(manifest_pin, terminal_pin):
    p.need(manifest_pin["sha256"] == PARENT_MANIFEST_SHA
           and terminal_pin["sha256"] == PARENT_TERMINAL_SHA, "Exact stopped v1 pins required")
    plan, terminal = p.checked(manifest_pin, parse=True), p.checked(terminal_pin, parse=True)
    p.RuntimeScope(manifest_pin, plan["jobs"][0]["provider_payload_sha256"]).verify()
    p.need(terminal["manifest_pin"] == manifest_pin and terminal["technically_complete"] is False
           and len(terminal["observations"]) == 1
           and terminal["observations"][0]["id"] == plan["jobs"][0]["id"]
           and terminal["observations"][0]["status"] == "halted"
           and terminal["unstarted_jobs"] == [j["id"] for j in plan["jobs"][1:]],
           "Only the exact seventeen unstarted original jobs may continue")
    first = terminal["observations"][0]
    actual = Path(plan["output"]) / "actual"
    p.need(not any((actual / j["id"]).exists() for j in plan["jobs"][1:])
           and sorted(actual.rglob("receipt.json")) == [Path(first["receipt_pin"]["path"])],
           "Additional original attempts prohibit suffix delivery")
    native = Path(first["receipt_pin"]["path"]).parent
    for name, field in (("sdk_request.json", "sdk_request_sha256"), ("wire_request.json", "wire_sha256")):
        raw = (native / name).read_bytes()
        p.need(sha256(raw).hexdigest() == first["receipt"][field]
               and p.contract.parse_json(raw) == plan["jobs"][0]["payload"], "Original request bytes differ")
    _decode(plan["jobs"][0], first)
    return plan, first


def prepare_continuation(output, parent_manifest_pin, parent_terminal_pin):
    parent, first = _parent(parent_manifest_pin, parent_terminal_pin)
    output = p.probe._regular(output).resolve()
    p.need(output.parent.is_dir() and not output.exists() and not output.is_relative_to(p.ROOT)
           and not output.is_relative_to(Path(parent["output"]))
           and not Path(parent["output"]).is_relative_to(output), "Fresh disjoint private continuation required")
    application, adaptation = _decode(parent["jobs"][0], first)
    recovered = {**deepcopy(first), "status": "valid", "application": application,
        "channel_delivery": adaptation, "historical_status": first["status"],
        "new_model_calls": 0, "cost_bookings_created": 0, "derived_read_only_view": True}
    output.mkdir(exist_ok=False)
    recovered_pin = p.save(output / "recovered-job-01.private.json", recovered)
    artifacts = [first[k] for k in ("receipt_pin", "raw_response_pin", "assistant_pin", "request_pin")]
    plan = {**deepcopy(parent), "protocol": PROTOCOL, "output": str(output),
        "jobs": deepcopy(parent["jobs"][1:]), "maximum_physical_POSTs": 17,
        "parent_manifest_pin": parent_manifest_pin, "parent_terminal_pin": parent_terminal_pin,
        "recovered_job_pin": recovered_pin,
        "source_pins": [*parent["source_pins"], parent_manifest_pin, parent_terminal_pin, recovered_pin, *artifacts],
        "code_pins": [*parent["code_pins"], p.pin(__file__), p.pin(Path(__file__).with_name("test_delivery_v2.py")),
                      p.pin(channels.__file__)], "historical_v1_modified": False,
        "delivery_change": "existing exact channel adapter; no output value, ID or judgment rewrite"}
    return p.save(output / "manifest.private.json", plan)


def _verify(manifest_pin):
    plan = p.checked(manifest_pin, parse=True)
    p.RuntimeScope(manifest_pin, plan["jobs"][0]["provider_payload_sha256"],
                   protocol=PROTOCOL, expected_jobs=17).verify()
    parent, first = _parent(plan["parent_manifest_pin"], plan["parent_terminal_pin"])
    p.need(plan["jobs"] == parent["jobs"][1:] and plan["maximum_physical_POSTs"] == 17
           and all(plan[k] == parent[k] for k in ("model", "expected_response_model", "HTTP_timeout_seconds",
                 "SDK_max_retries", "minimum_start_gap_seconds", "local_deadline_seconds")),
           "Original seventeen payloads and method parameters must remain unchanged")
    recovered = p.checked(plan["recovered_job_pin"], parse=True)
    application, _ = _decode(parent["jobs"][0], first)
    p.need(recovered["application"] == application and recovered["receipt"] == first["receipt"]
           and recovered["new_model_calls"] == recovered["cost_bookings_created"] == 0,
           "Recovered original must not create a request or cost booking")
    return plan, parent, recovered


def execute_suffix(manifest_pin, *, approved_manifest_sha256, config, wire=p.transport.azure_wire,
                   clock=time.monotonic, sleep=time.sleep):
    p.need(manifest_pin["sha256"] == approved_manifest_sha256, "Exact approved continuation required")
    plan, parent, recovered = _verify(manifest_pin)
    actual = p.probe._regular(Path(plan["output"]) / "actual")
    p.need(not actual.exists(), "Existing suffix cannot resume or replay")
    actual.mkdir(exist_ok=False)
    p.save(actual / "execution-start.private.json", {"manifest_pin": manifest_pin,
        "execution_kind": "provider" if wire is p.transport.azure_wire else "cpu_fakewire"})
    observations, started, last_start = [], clock(), None
    for job in plan["jobs"]:
        client, wire_calls = None, 0
        folder = actual / job["id"]
        obs = {**{k: deepcopy(job[k]) for k in ("id", "source_id", "arm", "draw", "stage")}, "status": "halted"}

        def once(current_config, payload, *, timeout):
            nonlocal wire_calls, last_start
            _verify(manifest_pin)
            p.need(wire_calls == 0 and timeout == 300 and p.digest(payload) == job["provider_payload_sha256"]
                   and clock() - started < p.DEADLINE, "One exact unstarted request within deadline required")
            wire_calls, last_start = 1, clock()
            return wire(current_config, payload, timeout=timeout)

        try:
            while last_start is not None and (delay := p.MIN_START_GAP - (clock() - last_start)) > 0:
                p.need(clock() - started < p.DEADLINE, "Local six-hour dispatch deadline reached")
                sleep(min(delay, 1.0))
            _verify(manifest_pin)
            p.need(clock() - started < p.DEADLINE, "Local six-hour dispatch deadline reached")
            obs["request_pin"] = p.save(folder / "declared-wire.private.json", job["payload"])
            scope = p.RuntimeScope(manifest_pin, job["provider_payload_sha256"], protocol=PROTOCOL, expected_jobs=17)
            client = p.private.SourceBoundClient(folder / "native", scope=scope, config=config, wire=once,
                model=plan["model"], expected_response_model=plan["expected_response_model"],
                thinking=None, timeout=300, clock=clock, max_physical_posts=1)
            client.phase = "relation_guard"
            response = client.client.chat.completions.create(**deepcopy(job["payload"]))
            obs["assistant_pin"] = p.save(folder / "assistant-original.utf8", response.choices[0].message.content.encode("utf8"))
            obs.update(receipt=deepcopy(client.receipts[-1]), receipt_pin=p.pin(client.output / "calls/0000/receipt.json"),
                raw_response_pin=p.pin(client.output / client.receipts[-1]["private_response_body_path"]))
            obs["application"], obs["channel_delivery"] = _decode(job, obs)
            obs["status"] = "valid"
        except BaseException as error:
            obs["error_class"] = type(error).__name__
            obs["application"] = p.guard.apply_response(job["case"]["source"]["text"],
                                                        job["case"]["inventory"], technical_failure=True)
        finally:
            obs["wire_invocations"] = wire_calls
            if client is not None:
                if client.receipts:
                    obs.update(receipt=deepcopy(client.receipts[-1]), receipt_pin=p.pin(client.output / "calls/0000/receipt.json"))
                client.client.close()
            observations.append(obs)
            p.save(folder / "observation.private.json", obs)
        print(p.canonical({"job_id": job["id"], "status": obs["status"], "count": len(observations)}).decode(), flush=True)
        if obs["status"] != "valid":
            break
    combined = [recovered, *observations]
    complete = len(combined) == 18 and all(o["status"] == "valid" for o in combined)
    return p.save(actual / "terminal.private.json", {"protocol": PROTOCOL, "manifest_pin": manifest_pin,
        "execution_kind": "provider" if wire is p.transport.azure_wire else "cpu_fakewire",
        "observations": combined, "technically_complete": complete,
        "gate": p.evaluate_gate(parent, combined) if complete else None,
        "unstarted_jobs": [j["id"] for j in plan["jobs"][len(observations):]],
        "old_request_count": 1, "recovered_new_model_calls": 0, "recovered_cost_bookings": 0,
        "cost_references": [o["receipt_pin"] for o in combined if "receipt_pin" in o],
        "automatic_retry_or_replay": False, "historical_v1_modified": False, "actual_money_cost": None})
