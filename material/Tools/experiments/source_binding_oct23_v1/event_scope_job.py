"""Frozen 32-call EV/VV source-scope development; preparation is offline.

The original AST prompt assembler, schemas and parser remain unchanged. Only
the SCOPE system instruction gains LF LF and a separately frozen clause.
No source-only evaluation references are decoded by this constructor.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
from datetime import datetime, timezone
from hashlib import sha256
import importlib.metadata
import importlib.util
import json
from pathlib import Path
import sys
import time
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[3]
EE_RUNNER = Path(__file__).with_name("runner.py")
EE_OUTPUT = Path('withheld-artifact/42a7b3ce21ff286d1c2e')
EE_PLAN_SHA = "e664e9e90c726efa417ab90eb29e87f51120f745ed746fd0d0ab3ab60b2a5c9f"
FIXTURES = ROOT / "Tools/experiments/greenfield_kgc_oct15_v8/fixtures_benchie_large_v8.json"
FIXTURE_IDS = ("be40", "be43", "be64")
DEFAULT_OUTPUT = Path('withheld-artifact/356bc1015fb4399461e0')
CHANNELS = ("event_entity", "event_relation")
PARAMETERS = {"model": "deepseek.v3.2", "temperature": 0.7,
              "max_tokens": 8192, "stream": False}
PROTOCOL = "event-scope-four-source-two-draw-development:oct23-v1"
STAGES = {"1": {"ordinals": list(range(1, 17)), "maximum_POSTs": 16},
          "2": {"ordinals": list(range(17, 33)), "maximum_POSTs": 16,
                "prerequisite": "Stage1 complete with all16 known valid responses and unchanged pins"}}


def frozen_runner():
    # Prepare binds the actual current helper, not an assumed historical SHA.
    # Verify checks this file again through the externally frozen plan bindings.
    spec = importlib.util.spec_from_file_location("event_scope_frozen_ee", EE_RUNNER)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def load_config(ee, path):
    binding = ee.pin(path)
    value = json.loads(ee.exact(binding))
    ee.require(type(value) is dict and set(value) <= {
        "clauses", "evaluator_plan", "hash_only_bindings"}, "Unknown config field")
    ee.require(set(value.get("clauses", {})) == set(CHANNELS), "Both EV/VV clauses required")
    for clause in value["clauses"].values():
        ee.require(type(clause) is str and bool(clause.strip()), "Nonempty exact scope clause required")
    refs = [value["evaluator_plan"], *value.get("hash_only_bindings", [])]
    for ref in refs:
        ee.require(type(ref) is dict and set(ref) == {"path", "bytes", "sha256"},
                   "Explicit hash-only evaluator pin required")
        ee.exact(ref)  # Hash and byte count only; never JSON-decode its contents.
    return value, binding, refs


def original_batches(original, text):
    prompts, schemas, method, _scope = original.existing.native_tools()
    batches = method(SimpleNamespace(prompt_instructions=prompts, result_schema=schemas),
                     [{"text": text, "metadata": {"lang": "en"}}])
    return batches, schemas


def scope_messages(ee, messages, clause, arm):
    result = deepcopy(messages)
    ee.require(type(result) is list and result and result[0].get("role") == "system"
               and type(result[0].get("content")) is str, "Original system message required")
    ee.require(arm in {"O", "SCOPE"}, "Declared original/scope arm required")
    if arm == "SCOPE":
        result[0]["content"] += "\n\n" + clause
    return result


def cpu_check(ee, config, original, repair, jsonschema):
    """No dispatch and no writes; test original format and exact intervention."""
    batches, schemas = original_batches(original, "A person described an event.")
    checks = []
    for channel in CHANNELS:
        base = batches[channel][0]
        original_arm = scope_messages(ee, base, config["clauses"][channel], "O")
        scoped = scope_messages(ee, base, config["clauses"][channel], "SCOPE")
        ee.require(original_arm == base and scoped[1:] == base[1:], "O/other-message drift")
        restored = deepcopy(scoped)
        restored[0]["content"] = restored[0]["content"][:-len("\n\n" + config["clauses"][channel])]
        ee.require(restored == base, "SCOPE delta exceeds system-only clause")
        fixture = ([{"Event": "A described B.", "Entity": ["A", "B"]}]
                   if channel == "event_entity" else
                   [{"Head": "A happened.", "Relation": "before", "Tail": "B happened."}])
        for expected in ([], fixture):
            raw = json.dumps(expected, ensure_ascii=False)
            for text in (raw, "```json\n" + raw + "\n```"):
                parsed, diagnosis = ee.parse_and_diagnose(text, schemas[channel], original,
                                                         repair, jsonschema)
                ee.require(parsed == expected and diagnosis["lossless_optional_wrapper_values_equal_native"],
                           "Original EV/VV parser/schema functional parity failed")
                checks.append({"channel": channel, "whole_fence": text != raw,
                               "native_objects": len(expected), "passed": True})
        wrong = ([{"Head": "a", "Relation": "b", "Tail": "c"}]
                 if channel == "event_entity" else [{"Event": "a", "Entity": ["b"]}])
        try:
            ee.parse_and_diagnose(json.dumps(wrong), schemas[channel], original, repair, jsonschema)
        except (ValueError, TypeError, jsonschema.ValidationError):
            checks.append({"channel": channel, "wrong_category_rejected": True, "passed": True})
        else:
            raise ValueError("Wrong-category native value was admitted")
    return {"protocol": PROTOCOL, "new_provider_calls": 0, "checks": checks,
            "O_original_AST_parity": True, "SCOPE_only_system_clause": True,
            "original_EV_VV_format_parity": True, "semantic_quality_evaluated": False}


def source_inputs(ee, parent, original):
    source = parent["sources"][0]
    raw = ee.exact(source["source_pin"])
    ee.require(source["delivered_span"] == {"coordinate_system": "raw_file_bytes", "start": 0,
               "end_exclusive": len(raw)}, "Complete original Stearns source required")
    rows = [{"source_id": source["source_id"], "cluster_id": source["cluster_id"],
             "raw": raw, "origin": source["source_pin"], "origin_kind": "original_file"}]
    fixtures_pin = ee.pin(FIXTURES)
    fixtures = json.loads(ee.exact(fixtures_pin))["fixtures"]
    for ident in FIXTURE_IDS:
        matches = [row for row in fixtures if row["id"] == ident]
        ee.require(len(matches) == 1, "Exactly one fixed fixture required")
        fixture = matches[0]
        raw = fixture["text"].encode("utf8")
        ee.require(sha256(raw).hexdigest() == fixture["source_text_sha256"], "Fixture text hash differs")
        rows.append({"source_id": ident, "cluster_id": "benchie:" + str(fixture["original_source_id"]),
                     "raw": raw, "origin": fixtures_pin, "origin_kind": "fixtures[].text",
                     "fixture_original_source_id": fixture["original_source_id"]})
    for row in rows:
        row["normalized"] = original.existing.normalize(row["raw"].decode("utf8"))
    return rows, fixtures_pin


def prepare(output, config_path, hash_only_paths=()):
    ee = frozen_runner()
    output = Path(output).resolve()
    ee.require(not output.exists(), "Fresh namespace only; no replay or implicit resume")
    config, config_pin, refs = load_config(ee, config_path)
    refs += [ee.pin(path) for path in hash_only_paths]
    parent, parent_pin = ee.verify_plan(EE_OUTPUT, EE_PLAN_SHA)
    ee.require(parent["parameters"] == PARAMETERS, "Original DeepSeek condition drift")
    original, repair, jsonschema = ee.helpers()
    source_rows, fixtures_pin = source_inputs(ee, parent, original)
    checked = cpu_check(ee, config, original, repair, jsonschema)
    module, _old, policy = original.reused()  # Definitions only; never invokes run().
    sources, rows = [], []
    for source in source_rows:
        raw_pin = ee.save(output / "input" / (source["source_id"] + ".raw.txt"), source["raw"])
        normalized_pin = ee.save(output / "input" / (source["source_id"] + ".native.txt"), source["normalized"].encode("utf8"))
        sources.append({k: v for k, v in source.items() if k not in {"raw", "normalized"}} |
                       {"source_pin": raw_pin, "normalized_source_pin": normalized_pin})
        batches, schemas = original_batches(original, source["normalized"])
        for arm, repeat in (("O", 1), ("SCOPE", 1), ("SCOPE", 2), ("O", 2)):
            for channel in CHANNELS:
                ordinal = len(rows) + 1
                messages = scope_messages(ee, batches[channel][0], config["clauses"][channel], arm)
                request = ee.save(output / "requests" / f"{ordinal:02d}.json",
                                  ee.canonical({**PARAMETERS, "messages": messages}))
                rows.append({"ordinal": ordinal, "source_id": source["source_id"],
                    "cluster_id": source["cluster_id"], "arm": arm, "repeat": repeat,
                    "channel": channel, "request": request, "schema": schemas[channel],
                    "messages_sha256": sha256(ee.canonical(messages)).hexdigest(),
                    "schema_sha256": sha256(ee.canonical(schemas[channel])).hexdigest()})
    imported = []
    for loaded in tuple(sys.modules.values()):
        file = getattr(loaded, "__file__", None)
        if file:
            path = Path(file).resolve()
            if path.is_file() and (path.is_relative_to(ROOT) or path.is_relative_to(ee.NATURAL.parent.parent)):
                imported.append(path)
    explicit = [Path(__file__), EE_RUNNER, ee.NATURAL, original.REUSED, module.ORIGINAL,
                module.BRIDGE, Path(repair.__file__), Path(jsonschema.__file__)]
    explicit += [ROOT / relative for relative in policy.SOURCE_PINS]
    bindings = [ee.pin(path) for path in dict.fromkeys([*explicit, *imported])]
    bindings += [parent_pin, config_pin, fixtures_pin, *refs, *parent["bindings"]]
    for source in sources:
        bindings += [source["origin"], source["source_pin"], source["normalized_source_pin"]]
    bindings += [row["request"] for row in rows]
    check_pin = ee.save(output / "cpu-check.json", checked)
    bindings.append(check_pin)
    plan = {"protocol": PROTOCOL, "created_utc": datetime.now(timezone.utc).isoformat(),
        "phase": "exposed_development_not_confirmation", "bindings": bindings,
        "parent_EE_plan": parent_pin, "config": config_pin, "sources": sources,
        "clauses": config["clauses"], "clause_sha256": {key: sha256(value.encode()).hexdigest()
            for key, value in config["clauses"].items()}, "evaluator_references_HASH_ONLY": refs,
        "reference_values_loaded_by_constructor": False, "rows": rows,
        "parameters": PARAMETERS, "HTTP_timeout_seconds": 300, "endpoint": module.URL,
        "requested_model": "deepseek.v3.2", "expected_reported_model": "deepseek.v3.2",
        "top_p": "omitted", "reasoning": "omitted_provider_default", "context_limit": None,
        "loaded_weight_revision": None, "planned_constructor_calls": 32,
        "maximum_physical_POSTs_this_plan": 32, "retries": 0, "unknown_execution_replay": False,
        "execution_stages": deepcopy(STAGES),
        "schedule": "source order; O1,SCOPE1,SCOPE2,O2; each EV then VV; serial",
        "prompt_policy": "Original AST; SCOPE appends LF LF plus channel clause to system only",
        "parser_policy": parent["native_parser"], "format_policy": parent["format_policy"],
        "stop_policy": "First unknown, transport, model, parameter, parser or schema failure stops. No resend/resume.",
        "runtime_versions": {name: importlib.metadata.version(name) for name in ("json-repair", "jsonschema", "openai")},
        "cpu_check": check_pin, "semantic_quality_evaluated": False, "new_provider_calls": 0,
        "full_KGC_construction": False, "actual_cost_USD": None}
    return ee.save(output / "plan.json", plan)


def verify(output, expected):
    ee = frozen_runner()
    binding = ee.pin(Path(output) / "plan.json")
    ee.require(binding["sha256"] == expected, "Externally retained frozen plan SHA required")
    plan = json.loads(ee.exact(binding))
    for item in plan["bindings"]:
        ee.exact(item)
    config, _, _refs = load_config(ee, plan["config"]["path"])
    ee.require(config["clauses"] == plan["clauses"], "Frozen clauses changed")
    ee.require(plan["parameters"] == PARAMETERS and plan["HTTP_timeout_seconds"] == 300,
               "Frozen constructor settings changed")
    ee.require(plan["planned_constructor_calls"] == plan["maximum_physical_POSTs_this_plan"]
               == len(plan["rows"]) == 32, "Exactly32 immutable call positions required")
    ee.require(plan["execution_stages"] == STAGES, "Frozen stage boundaries changed")
    original, repair, jsonschema = ee.helpers()
    cpu_check(ee, config, original, repair, jsonschema)
    expected_rows = []
    for source in plan["sources"]:
        text = original.existing.normalize(ee.exact(source["source_pin"]).decode("utf8"))
        ee.require(text.encode() == ee.exact(source["normalized_source_pin"]), "Source normalization drift")
        batches, schemas = original_batches(original, text)
        for arm, repeat in (("O", 1), ("SCOPE", 1), ("SCOPE", 2), ("O", 2)):
            for channel in CHANNELS:
                row = plan["rows"][len(expected_rows)]
                expected_rows.append((source["source_id"], arm, repeat, channel))
                ee.require((row["source_id"], row["arm"], row["repeat"], row["channel"])
                           == expected_rows[-1], "Bound schedule changed")
                payload = json.loads(ee.exact(row["request"]))
                ee.require({k: v for k, v in payload.items() if k != "messages"} == PARAMETERS,
                           "Unexpected sampling/reasoning/model field")
                messages = scope_messages(ee, batches[channel][0], config["clauses"][channel], arm)
                ee.require(payload["messages"] == messages and row["messages_sha256"]
                           == sha256(ee.canonical(messages)).hexdigest(), "Original/SCOPE prompt drift")
                ee.require(row["schema"] == schemas[channel] and row["schema_sha256"]
                           == sha256(ee.canonical(schemas[channel])).hexdigest(), "Native schema drift")
    ee.require([row["ordinal"] for row in plan["rows"]] == list(range(1, 33)), "Complete ordinals required")
    ee.require(len(plan["sources"]) == 4 and [s["source_id"] for s in plan["sources"]][1:]
               == list(FIXTURE_IDS), "Fixed four-source population changed")
    return plan, binding


def completed_stage_one(ee, output, plan):
    """Stage2 cannot bypass a failed/unknown Stage1 or replay its requests."""
    binding = ee.pin(output / "terminal-construction-stage1.json")
    prior = json.loads(ee.exact(binding))
    ee.require(prior["plan"]["sha256"] == ee.pin(output / "plan.json")["sha256"]
               and prior["stage"] == 1 and prior["status"] == "complete"
               and prior["attempts"] == 16 and prior["failure"] is None
               and len(prior["observations"]) == 16, "Stage1 must have16 known valid completions")
    for observation, row in zip(prior["observations"], plan["rows"][:16]):
        ee.require(all(observation[key] == row[key] for key in
            ("ordinal", "source_id", "cluster_id", "channel", "arm", "repeat")), "Stage1 row identity drift")
        for key in ("assistant_pin", "parsed_pin", "format_diagnostic_pin", "assertions_pin"):
            ee.exact(observation[key])
        receipt = observation["receipt"]
        ee.require(receipt.get("http_status") == 200 and receipt.get("finish_reason") == "stop"
            and receipt.get("HTTP_body_complete") is True and not receipt.get("unknown_execution", False)
            and receipt.get("POST_attempts") == 1, "Stage1 contains unknown or incomplete execution")
    return binding


def execute(output, expected, stage):
    ee = frozen_runner()
    output = Path(output).resolve()
    plan, plan_pin = verify(output, expected)
    ee.require(stage in {1, 2}, "Explicit stage1 or stage2 required")
    rows = plan["rows"][:16] if stage == 1 else plan["rows"][16:]
    stage_root = output / f"stage-{stage}"
    marker = output / f"execution-start-stage{stage}.json"
    ee.require(not stage_root.exists() and not marker.exists(),
               "No replay or implicit resume")
    prerequisite = completed_stage_one(ee, output, plan) if stage == 2 else None
    original, repair, jsonschema = ee.helpers()
    module, old, policy = original.reused()
    module.BASE, module.HTTP = stage_root, 300

    class BoundedWire(module.Wire):
        def __call__(self, config, payload, *, timeout):
            ee.require(len(self.rows) == 16 and self.attempts < 16, "16 physical POST ceiling for this stage")
            return super().__call__(config, payload, timeout=timeout)

    from Tools.abschluss.hipporag2_foundry_client_v1 import _private_directory
    (stage_root / "actual").mkdir(mode=0o700, parents=True)
    _private_directory(output)
    _private_directory(stage_root)
    _private_directory(stage_root / "actual")
    wire = BoundedWire(old, rows)
    config = old.probe.Config(url=module.URL, key=old.load_key(),
                             host_type="bedrock-mantle", project_endpoint_valid=False)
    observations, failure = [], None
    started = time.monotonic()
    ee.save(marker, {"plan": plan_pin, "stage": stage, "stage1_terminal": prerequisite,
        "bound_ordinals": [row["ordinal"] for row in rows],
        "utc": datetime.now(timezone.utc).isoformat(), "retries": 0})
    for row in rows:
        active = None
        attempts_before = wire.attempts
        try:
            # Full AST/schema/parity verification preceded this stage. Recheck
            # all immutable files before each POST without rebuilding32 prompts.
            ee.require(ee.pin(output / "plan.json")["sha256"] == expected, "Frozen plan changed")
            for item in plan["bindings"]:
                ee.exact(item)
            payload = json.loads(ee.exact(row["request"]))
            active = policy.MantleClient(stage_root / "actual" / f"task-{row['ordinal']:04d}",
                config=config, wire=wire, model=plan["requested_model"],
                expected_response_model=plan["expected_reported_model"], timeout=300,
                thinking=None, max_physical_posts=1)
            active.phase = "event-scope-development"
            response = active.client.chat.completions.create(**payload)
            choice = response.choices[0]
            text = choice.message.content
            raw_pin = None
            if type(text) is str:
                raw_pin = ee.save(active.output / "native-assistant-original.utf8", text.encode("utf8"))
            ee.require(choice.finish_reason == "stop" and type(text) is str and bool(text.strip()),
                       "Complete nonempty stop required")
            parsed, diagnostic = ee.parse_and_diagnose(text, row["schema"], original, repair, jsonschema)
            parsed_pin = ee.save(active.output / "native-parsed-original.json", parsed)
            diagnostic_pin = ee.save(active.output / "format-diagnostic.json", diagnostic)
            occurrences = ee.save(active.output / "assertion-occurrences.json",
                [{"native_index": i, "value": value} for i, value in enumerate(parsed)])
            observation = {**{key: row[key] for key in
                ("ordinal", "source_id", "cluster_id", "channel", "arm", "repeat")},
                "native_records": len(parsed), "assistant_pin": raw_pin, "parsed_pin": parsed_pin,
                "format_diagnostic_pin": diagnostic_pin, "assertions_pin": occurrences,
                "receipt": active.receipts[-1]}
            observations.append(observation)
            ee.save(stage_root / "completed" / f"{row['ordinal']:02d}.json", observation)
            print(json.dumps({"completed": len(observations), "attempts": wire.attempts}), flush=True)
        except BaseException as error:
            receipt = active.receipts[-1] if active is not None and active.receipts else {}
            dispatched = wire.attempts > attempts_before
            unknown = dispatched and (bool(receipt.get("unknown_execution"))
                or not receipt.get("HTTP_body_complete", False))
            failure = {"ordinal": row["ordinal"], "channel": row["channel"],
                "error_class": type(error).__name__, "receipt": receipt,
                "status": "unknown_execution" if unknown else "known_completed_technical_failure"
                    if dispatched else "pre_dispatch_technical_failure",
                "dispatch_attempted": dispatched,
                "raw_response_preserved_by_transport": dispatched, "retry_performed": False}
            break
        finally:
            if active is not None:
                active.client.close()
    result = {"protocol": PROTOCOL, "plan": plan_pin, "stage": stage,
        "stage1_terminal": prerequisite,
        "status": "complete" if failure is None and len(observations) == 16 else "stopped",
        "observations": observations, "failure": failure, "attempts": wire.attempts,
        "bound_ordinals": [row["ordinal"] for row in rows],
        "unstarted_ordinals": [row["ordinal"] for row in rows[wire.attempts:]],
        "client_seconds": time.monotonic() - started, "retries": 0,
        "actual_cost_USD": None, "semantic_quality_evaluated": False, "full_KGC_construction": False}
    binding = ee.save(output / f"terminal-construction-stage{stage}.json", result)
    print(json.dumps({"terminal": binding, "status": result["status"]}), flush=True)
    return 0 if result["status"] == "complete" else 2


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--prepare", action="store_true")
    mode.add_argument("--cpu-check", action="store_true")
    mode.add_argument("--verify-plan-sha256")
    mode.add_argument("--execute-plan-sha256")
    parser.add_argument("--config", type=Path)
    parser.add_argument("--hash-only-binding", type=Path, action="append", default=[],
                        help="Additional evaluator-only file to hash without decoding; prepare only")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--stage", type=int, choices=(1, 2), help="Required for actual execution; never auto-continue")
    args = parser.parse_args()
    if args.prepare:
        parser.error("--prepare requires --config") if args.config is None else None
        print(json.dumps(prepare(args.output, args.config, args.hash_only_binding)))
    elif args.cpu_check:
        parser.error("--cpu-check requires --config") if args.config is None else None
        ee = frozen_runner()
        config, _pin, _refs = load_config(ee, args.config)
        print(json.dumps(cpu_check(ee, config, *ee.helpers())))
    elif args.verify_plan_sha256:
        _plan, pin = verify(args.output, args.verify_plan_sha256)
        print(json.dumps({"verified": pin, "new_provider_calls": 0}))
    else:
        parser.error("--execute-plan-sha256 requires --stage") if args.stage is None else None
        raise SystemExit(execute(args.output, args.execute_plan_sha256, args.stage))
