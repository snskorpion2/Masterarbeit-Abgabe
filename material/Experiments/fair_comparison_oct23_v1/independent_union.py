"""Offline U3 repeat preparation and exact whole-object union.

No transport, credentials, model libraries or dispatch live here. The repeat
receives only the three original source-only payloads. Original parser functions
are compiled unchanged from their verified AST, as in existing native audits.
Whole EV values are indivisible. Equality is exact typed JSON equality, never
event-text matching, participant merging, case folding or semantic deduplication.
"""
from __future__ import annotations

import ast
from contextlib import redirect_stderr, redirect_stdout
from copy import deepcopy
import hashlib
import io
import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Dict, List

import json_repair
import jsonschema

from Experiments.strict_autoschemakg.contract import DEFAULT_SOURCE, parse_json, verify_source
from Experiments.strict_autoschemakg.immutable_publish import publish_bytes

ROOT = Path(__file__).resolve().parents[2]
PROTOCOL = "fair-independent-original-extraction-union-U3-oct23-v1"
CATEGORIES = ("entity_relation", "event_entity", "event_relation")
EXPECTED_BASELINE_SHA = "2af3e01d685e6bf3ee85403e0429ef06ed8b67ad55b27cafce2c3bdaddee30d6"


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"), allow_nan=False).encode("utf8")


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def pin(path):
    path = Path(path).absolute()
    if path.is_symlink() or not path.is_file():
        raise ValueError("Regular original artifact required")
    raw = path.read_bytes()
    return {"path": str(path), "sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw)}


def bound(record):
    actual = pin(record["path"])
    if actual != record:
        raise ValueError("Pinned artifact changed: " + record["path"])
    return Path(record["path"]).read_bytes()


def _native(source=DEFAULT_SOURCE):
    """Only original literal constants, three pure validators and OutputParser."""
    source = Path(source)
    proof = verify_source(source)  # Includes all 69 original files and commit.
    helper = ROOT / "Tools/experiments/autoschema_ladder_oct14_v1/audit.py"
    tree = ast.parse(helper.read_bytes())
    literal_node = next(n for n in tree.body if isinstance(n, ast.FunctionDef)
                        and n.name == "literal_constants")
    helper_ns = {"ast": ast, "Path": Path}
    exec(compile(ast.Module(body=[literal_node], type_ignores=[]), str(helper), "exec"), helper_ns)
    schema_path = source / "atlas_rag/llm_generator/format/validate_json_schema.py"
    prompt_path = source / "atlas_rag/llm_generator/prompt/triple_extraction_prompt.py"
    schemas = helper_ns["literal_constants"](schema_path)["ATLAS_SCHEMA"]
    prompts = helper_ns["literal_constants"](prompt_path)["TRIPLE_INSTRUCTIONS"]
    validator_path = source / "atlas_rag/llm_generator/format/validate_json_output.py"
    wanted = {"normalize_key", "fix_triple_extraction_response", "validate_output"}
    definitions = [n for n in ast.parse(validator_path.read_bytes()).body
                   if isinstance(n, ast.FunctionDef) and n.name in wanted]
    if {n.name for n in definitions} != wanted:
        raise ValueError("Complete original pure parser definitions required")
    namespace = {"json": json, "json_repair": json_repair, "jsonschema": jsonschema,
                 "List": List, "Dict": Dict, "Any": Any}
    exec(compile(ast.Module(body=definitions, type_ignores=[]), str(validator_path), "exec"), namespace)
    parser_path = source / "atlas_rag/kg_construction/triple_extraction.py"
    parser = next(n for n in ast.parse(parser_path.read_bytes()).body
                  if isinstance(n, ast.ClassDef) and n.name == "OutputParser")
    exec(compile(ast.Module(body=[parser], type_ignores=[]), str(parser_path), "exec"), namespace)
    paths = [Path(__file__), helper, schema_path, prompt_path, validator_path, parser_path,
        source / "atlas_rag/llm_generator/llm_generator.py",
        ROOT / "Experiments/strict_autoschemakg/contract.py",
        ROOT / "Experiments/strict_autoschemakg/immutable_publish.py",
        Path(json_repair.__file__), Path(jsonschema.__file__)]
    return SimpleNamespace(proof=proof, schemas=schemas, prompts=prompts,
        validate=namespace["validate_output"], fix=namespace["fix_triple_extraction_response"],
        parser=namespace["OutputParser"](), code_pins=[pin(p) for p in paths])


def parse_native(category, raw_response, *, source=DEFAULT_SOURCE, native=None):
    """Replay the unchanged native Pipeline validator and OutputParser route."""
    if category not in CATEGORIES or type(raw_response) is not str:
        raise ValueError("Original category and raw text required")
    native = native or _native(source)
    capture = io.StringIO()
    with redirect_stdout(capture), redirect_stderr(capture):
        validated = native.validate(raw_response.strip(), schema=native.schemas[category],
                                    fix_function=native.fix, allow_empty=True)
        normalized = validated.split("</think>")[-1].strip() if "</think>" in validated else validated
        values = native.parser.extract_structured_data([normalized])[0]
    return {"values": values, "native_output": normalized,
            "native_validator_log": capture.getvalue(),
            "original_response_sha256": hashlib.sha256(raw_response.encode("utf8")).hexdigest(),
            "parsed_array_sha256": digest(values)}


def prepare_u3(prefix, output, *, expected_handoff_sha256, source=DEFAULT_SOURCE):
    """Create three source-only payloads after exact original prefix replay."""
    prefix, output = Path(prefix), Path(output)
    if output.exists():
        raise ValueError("Fresh U3 preparation directory required")
    handoff_pin = pin(prefix / "AS-extraction-prefix-handoff.json")
    if handoff_pin["sha256"] != expected_handoff_sha256:
        raise ValueError("Explicit original prefix handoff differs")
    handoff = parse_json(bound(handoff_pin).decode("utf8"))
    if (handoff.get("prefix_complete") is not True or handoff.get("physical_POSTs") != 3
            or handoff.get("unknown_executions") != 0):
        raise ValueError("Exactly three confirmed original category calls required")
    for record in handoff["files"].values():
        bound(record)
    baseline_pin = pin(ROOT / "Experiments/fair_comparison_oct23_v1/baseline.py")
    if baseline_pin["sha256"] != EXPECTED_BASELINE_SHA:
        raise ValueError("Named production baseline changed")
    rows_pin, source_pin = (handoff["files"][name] for name in ("native_rows.json", "sources.json"))
    rows, sources = (parse_json(bound(p).decode("utf8")) for p in (rows_pin, source_pin))
    chunks = parse_json(bound(handoff["files"]["source_chunks.json"]).decode("utf8"))
    if len(rows) != 1 or len(sources) != 1 or len(chunks) != 1:
        raise ValueError("U3 control requires one complete native source unit")
    original_row, document = rows[0], sources[0]
    if (document["sha256"] != hashlib.sha256(document["text"].encode("utf8")).hexdigest()
            or original_row["id"] != document["id"] or original_row["original_text"] != document["text"]
            or chunks[0]["text"] != document["text"]):
        raise ValueError("Complete original source bytes and identity differ")
    native = _native(source)
    language = document.get("metadata", {}).get("lang", "en")
    policy = deepcopy(handoff["policy"])
    expected_wire = {"model": "gpt-6-luna", "max_completion_tokens": 32768,
                     "reasoning_effort": "low", "n": 1, "stream": False}
    if canonical(policy["wire_parameters"]) != canonical(expected_wire):
        raise ValueError("Original Luna wire condition differs")
    requests, proofs, payloads = [], [], []
    for ordinal, category in enumerate(CATEGORIES):
        observed = parse_json(bound(handoff["files"][f"observed_calls/{ordinal:05d}/receipt.json"]).decode("utf8"))
        payload_raw = bound(handoff["files"][f"calls/{ordinal:05d}/request.json"])
        payload = parse_json(payload_raw.decode("utf8"))
        physical = parse_json(bound(handoff["files"][f"calls/{ordinal:05d}/receipt.json"]).decode("utf8"))
        response = parse_json(bound(handoff["files"][f"calls/{ordinal:05d}/provider-response.json"]).decode("utf8"))
        expected_messages = [{"role": "system", "content": native.prompts[language]["system"]},
            {"role": "user", "content": native.prompts[language][category] + "\n" + document["text"]}]
        if (observed["status"] != "completed" or observed["phase"] != "run_extraction"
                or payload["messages"] != expected_messages or observed["messages"] != expected_messages
                or canonical({k: v for k, v in payload.items() if k != "messages"}) != canonical(expected_wire)
                or physical.get("unknown_execution") is not False or physical.get("physical_POSTs") != 1
                or physical.get("finish_reason") != "stop"
                or physical.get("provider_model") != handoff["provider_model"]):
            raise ValueError("Source-only original messages, wire or terminal response differ")
        raw_response = response["choices"][0]["message"]["content"]
        if raw_response != observed["raw_response"]:
            raise ValueError("Provider body differs from original native observer")
        replay = parse_native(category, raw_response, native=native)
        if (canonical(replay["values"]) != canonical(original_row[category + "_dict"])
                or replay["native_output"] != original_row[category + "_output"]):
            raise ValueError("Original raw answer does not replay exactly to native prefix")
        relative = f"requests/{ordinal:02d}-{category}.json"
        requests.append({"ordinal": ordinal, "category": category,
            "request_id": "U3:independent-repeat:" + category, "payload_file": relative,
            "payload_sha256": hashlib.sha256(payload_raw).hexdigest(),
            "native_HF_parameters": deepcopy(observed["native_parameters"]),
            "messages_sha256": digest(expected_messages), "available_information": "source_only"})
        payloads.append((relative, payload_raw))
        proofs.append({"category": category, "original_request_pin": handoff["files"][f"calls/{ordinal:05d}/request.json"],
            "raw_response_sha256": replay["original_response_sha256"],
            "parsed_array_sha256": replay["parsed_array_sha256"], "whole_objects": len(replay["values"]),
            "native_output_text_identical": True, "parsed_array_identical": True})
    plan = {"protocol": PROTOCOL, "status": "prepared_not_dispatched", "construction_calls": 3,
        "source": deepcopy(document), "requests": requests, "actual_wire_parameters": expected_wire,
        "HTTP_timeout_seconds": policy["timeout_seconds"], "expected_provider_model": handoff["provider_model"],
        "transport_retries": 0, "automatic_native_validation_retries": 0,
        "unknown_execution": "halt; never resend or fabricate an empty category",
        "prefix_handoff_pin": handoff_pin, "original_native_rows_pin": rows_pin,
        "original_sources_pin": source_pin, "original_source_verification": native.proof,
        "parser_route": "Original validate_output/fix_triple_extraction_response; original Pipeline strip/think suffix; original OutputParser",
        "parser_code_pins": native.code_pins, "production_baseline_pin": baseline_pin,
        "baseline_answers_in_repeat_payload": False, "references_or_evaluation_inputs_loaded": False,
        "union_policy": "Exact whole typed JSON object equality within category; every original occurrence retained as a witness",
        "semantic_novelty_or_support_evaluated": False, "dispatch_performed": False}
    audit = {"protocol": PROTOCOL + ":original-parser-readback", "confirmed_categories": proofs,
        "original_commit": native.proof["commit"], "verified_original_files": len(native.proof["files"]),
        "model_library_imports_required": False, "model_calls": 0}
    output.mkdir(parents=True, exist_ok=False)
    for name, raw in payloads:
        publish_bytes(output / name, raw, same=lambda _: False)
    publish_bytes(output / "prefix-parser-readback.json", canonical(audit), same=lambda _: False)
    publish_bytes(output / "plan.json", canonical(plan), same=lambda _: False)
    return {"prepared_dir": str(output), "plan_pin": pin(output / "plan.json"),
            "parser_readback_pin": pin(output / "prefix-parser-readback.json"), "request_count": 3}


def load_prepared(plan_path, expected_plan_sha256):
    actual = pin(plan_path)
    if actual["sha256"] != expected_plan_sha256:
        raise ValueError("Externally retained U3 plan hash differs")
    plan = parse_json(bound(actual).decode("utf8"))
    if plan["protocol"] != PROTOCOL or plan["construction_calls"] != 3:
        raise ValueError("Original three-call U3 condition required")
    for record in [*plan["parser_code_pins"], plan["production_baseline_pin"],
                   plan["prefix_handoff_pin"], plan["original_native_rows_pin"], plan["original_sources_pin"]]:
        bound(record)
    parent = Path(plan_path).parent
    for request in plan["requests"]:
        raw = (parent / request["payload_file"]).read_bytes()
        if hashlib.sha256(raw).hexdigest() != request["payload_sha256"]:
            raise ValueError("Source-only payload changed")
    return plan


def parse_second_draw(plan_path, raw_by_category, *, expected_plan_sha256, source=DEFAULT_SOURCE):
    """No sends/retries: one original raw response per complete category."""
    plan = load_prepared(plan_path, expected_plan_sha256)
    if type(raw_by_category) is not dict or set(raw_by_category) != set(CATEGORIES):
        raise ValueError("Exactly three complete raw category responses required")
    native = _native(source)
    document = plan["source"]
    row = {"id": document["id"], "original_text": document["text"],
           "metadata": deepcopy(document.get("metadata", {}))}
    for category in CATEGORIES:
        parsed = parse_native(category, raw_by_category[category], native=native)
        row[category + "_dict"] = parsed["values"]
        row[category + "_output"] = parsed["native_output"]
    return row


def union_rows(first, second, *, first_draw_id, second_draw_id, source=DEFAULT_SOURCE):
    """Append exact whole objects, retaining all occurrence/draw witnesses."""
    if (type(first_draw_id) is not str or not first_draw_id or type(second_draw_id) is not str
            or not second_draw_id or first_draw_id == second_draw_id):
        raise ValueError("Two distinct nonempty draw identities required")
    for field in ("id", "original_text", "metadata"):
        if canonical(first.get(field)) != canonical(second.get(field)):
            raise ValueError("Union cannot combine different source units or metadata")
    native = _native(source)
    result = {field: deepcopy(first[field]) for field in ("id", "original_text", "metadata")}
    occurrences, outputs = [], []
    for category in CATEGORIES:
        field = category + "_dict"
        for row in (first, second):
            jsonschema.validate(row[field], native.schemas[category])
        result[field], positions = [], {}
        for draw_id, row in ((first_draw_id, first), (second_draw_id, second)):
            for index, value in enumerate(row[field]):
                identity = canonical(value)
                if identity not in positions:
                    positions[identity] = len(result[field])
                    result[field].append(deepcopy(value))
                    outputs.append({"category": category, "union_index": positions[identity],
                        "value_sha256": digest(value), "witnesses": []})
                union_index = positions[identity]
                witness = {"draw_id": draw_id, "source_id": row["id"], "category": category,
                    "input_index": index, "input_pointer": f"/{field}/{index}", "union_index": union_index,
                    "value_sha256": digest(value)}
                occurrences.append(witness)
                next(o for o in outputs if o["category"] == category and o["union_index"] == union_index)["witnesses"].append(deepcopy(witness))
    return {"protocol": PROTOCOL + ":exact-union", "native_row": result,
        "parents": [{"draw_id": first_draw_id, "native_row_sha256": digest(first)},
                    {"draw_id": second_draw_id, "native_row_sha256": digest(second)}],
        "whole_objects": outputs, "occurrences": occurrences,
        "all_original_occurrences_recoverable": True, "semantic_deduplication": False,
        "event_participant_merge": False, "semantic_quality_measured": False,
        "provider_raw_output_fields_fabricated": False}
