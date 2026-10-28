"""Execute the approved single-extraction Lamport repair pilot.

This mode collects raw evidence only. It intentionally does not compute outcome
means, item transitions, answer accuracy, calibration, or schema recall.
"""
from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import re
import subprocess
import sys
import time

from . import extended_artifacts as artifacts, extended_measurements as measure
from . import frozen_questions
from .retry_policy import transient_transport
from .contract import DEFAULT_SOURCE, new_output, sha256, verify_source, write_json
from .local_pilot import ARTICLE, REPOSITORY
from .local_runtime import LocalOllama, PROFILES, request_json

QUESTIONS = (REPOSITORY / "Experiments/results/strict_autoschemakg/"
             "local_lamport_pilot_v3/questions/native/mcq.jsonl")
CONSTRUCTOR = "nvidia/NVIDIA-Nemotron-3-Nano-4B-BF16"
JUDGE = "Qwen/Qwen3.5-4B"
CONTEXTS = ("empty", "passage", "entity", "event_only", "event")
CONFIDENCE_BATCH = 8
MCQ_CONFIDENCE_BATCH = 4
OUTPUT_TOKENS = {"confidence_per_item": 256,
                 "confidence_overhead": 128, "mcq": "native_remaining_context"}
NATIVE_PROMPT_MARKERS = (
    "The given entity relationship recognition results as follows:",
    "The given entity recognition results as followed:",
    "The given event relationship recognition results as followed:",
    "The model entity relationship recognition results as follows:",
    "The model named entity recognition results as followed:",
    "The model event relationship recognition results as followed:",
)
NATIVE_CSV_COLUMNS = ("i", *(f"{metric}_{number}" for number in range(1, 4)
                             for metric in ("precision", "recall", "f1")))


def _reserve(request):
    if request["kind"] == "confidence":
        return OUTPUT_TOKENS["confidence_overhead"] + OUTPUT_TOKENS["confidence_per_item"] * len(request["item_ids"])
    return OUTPUT_TOKENS[request["kind"]]


def _now():
    return datetime.now(timezone.utc).isoformat()


def _append(path, value):
    with Path(path).open("a", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps(value, ensure_ascii=False, allow_nan=False) + "\n")
        stream.flush()
        os.fsync(stream.fileno())


def _records(path):
    from . import immutable_publish
    if not path.exists():
        return []
    values = []
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        try:
            values.append(immutable_publish.loads(line))
        except (json.JSONDecodeError, ValueError) as exc:
            raise ValueError(f"Incomplete checkpoint line {number}: {path}") from exc
    return values


def _one_file(directory, pattern):
    files = list(directory.glob(pattern))
    if len(files) != 1:
        raise ValueError(f"Expected exactly one {pattern} in {directory}, got {len(files)}")
    return files[0]


def _last_transport_record(path):
    from . import immutable_publish
    # Raw LocalOllama call log is append-only; read only its last line.
    with path.open("rb") as stream:
        stream.seek(0, 2)
        end = stream.tell()
        if end == 0:
            raise ValueError("Empty local transport call log")
        position = end - 1
        while position > 0:
            stream.seek(position - 1)
            if stream.read(1) == b"\n" and position < end:
                break
            position -= 1
        stream.seek(position)
        return immutable_publish.loads(stream.readline().decode("utf-8"))


def _classify(request, raw):
    kind = request["kind"]
    if kind == "mcq":
        answer = measure.parse_answer(raw, request["variant"])
        if answer is None:
            raise ValueError("Not exactly one allowed answer letter")
        return {"answer": answer, "abstained": answer == "E"}
    data = measure.parse_json_response(raw)
    if kind == "confidence":
        data, bridge = measure.confidence_container(data, request["item_ids"])
        return {"judgments": measure.validate_confidence(data, request["item_ids"]), "format_bridge": bridge}
    raise ValueError("Unknown sidecar request kind")


def _transport_hash(transport):
    return hashlib.sha256(json.dumps(transport, ensure_ascii=False,
                                     sort_keys=True).encode()).hexdigest()


def _transport_valid(transport, model):
    response = transport.get("response", {})
    expected = PROFILES[model]["ollama_model"]
    prompt_tokens = transport.get("hf_prompt_tokens")
    return ("transport_error" not in transport and transport.get("model") == expected
            and response.get("model") == expected and response.get("done") is True
            and type(prompt_tokens) is int and prompt_tokens >= 0
            and response.get("prompt_eval_count") == prompt_tokens
            and not response.get("thinking") and isinstance(response.get("response"), str))


def _recover_logged_calls(path, requests, existing, model):
    """Recover a raw answer logged just before interruption, without sampling it again."""
    known = {entry.get("transport_call_sha256") for entry in existing.values()}
    for transport in _records(path / "calls.jsonl"):
        digest = _transport_hash(transport)
        if digest in known:
            continue
        messages = transport.get("messages", [])
        prompt = messages[-1].get("content") if messages else None
        pending = next((request for request in requests
                        if request["request_id"] not in existing
                        and request["prompt"] == prompt), None)
        if pending is None:
            raise ValueError("Unmatched raw transport call in sidecar checkpoint")
        record = {key: pending[key] for key in ("request_id", "kind", "item_ids")}
        record.update(model=model, prompt_sha256=hashlib.sha256(prompt.encode()).hexdigest(),
                      output_reserve_tokens=_reserve(pending), transport_call_sha256=digest,
                      model_digest=PROFILES[model]["ollama_digest"],
                      recovered_from_transport_log=True)
        if "variant" in pending:
            record["variant"] = pending["variant"]
        response = transport.get("response", {})
        record["done_reason"] = response.get("done_reason")
        raw = response.get("response")
        if isinstance(raw, str):
            record["raw_response"] = raw
        if not _transport_valid(transport, model):
            record.update(status="transport_error", error_type="LoggedTransportError")
            record["retry_allowed"] = transport.get("transport_error", {}).get("retryable_transient") is True
        elif response.get("done_reason") == "length":
            record.update(status="length_abort", error_type="OutputLimit")
        else:
            try:
                record.update(status="valid", parsed=_classify(pending, raw))
            except (ValueError, TypeError, KeyError):
                record.update(status="invalid_format", error_type="ResponseContract")
        record["transport_elapsed_seconds"] = transport.get("elapsed_seconds")
        record["usage"] = {key: response.get(key) for key in ("prompt_eval_count", "eval_count", "total_duration")}
        _append(path / "responses.jsonl", record)
        existing[record["request_id"]] = record
        known.add(digest)


def _requests_once(path, requests, model):
    """Persist one raw result per deterministic request; never redraw recorded IDs."""
    path.mkdir(parents=True, exist_ok=True)
    destination = path / "responses.jsonl"
    recorded = _records(destination)
    existing = {entry["request_id"]: entry for entry in recorded}
    if len(existing) != len(recorded):
        raise ValueError("Duplicate response checkpoint ID")
    requested = {entry["request_id"] for entry in requests}
    if len(requested) != len(requests) or set(existing) - requested:
        raise ValueError("Sidecar request schedule changed on resume")
    by_id = {request["request_id"]: request for request in requests}
    for ident, entry in existing.items():
        request = by_id[ident]
        if (entry.get("prompt_sha256") != hashlib.sha256(request["prompt"].encode()).hexdigest()
                or entry.get("model") != model):
            raise ValueError("Sidecar checkpoint prompt or model changed")
    _recover_logged_calls(path, requests, existing, model)
    known_transport_hashes = {entry.get("transport_call_sha256") for entry in existing.values()}
    pending = [request for request in requests if request["request_id"] not in existing]
    if not pending:
        return list(existing.values())
    runtime = None
    try:
        for request in pending:
            started = time.perf_counter()
            record = {key: request[key] for key in ("request_id", "kind", "item_ids")}
            record.update(model=model, model_digest=PROFILES[model]["ollama_digest"],
                          prompt_sha256=hashlib.sha256(request["prompt"].encode()).hexdigest(),
                          output_reserve_tokens=_reserve(request))
            if "variant" in request:
                record["variant"] = request["variant"]
            if request.get("skip_reason"):
                record.update(status="missing_dependency", error_code=request["skip_reason"],
                              elapsed_seconds=0.0)
                _append(destination, record)
                existing[record["request_id"]] = record
                continue
            if runtime is None:
                runtime = LocalOllama(model, path)
            try:
                parameters = ({} if request["kind"] == "mcq" else
                              {"max_new_tokens": _reserve(request)})
                raw = runtime.generate([{"role": "user", "content": request["prompt"]}], parameters)
                record["raw_response"] = raw
                transport = _last_transport_record(path / "calls.jsonl")
                response = transport.get("response", {})
                record["done_reason"] = response.get("done_reason")
                record["transport_call_sha256"] = _transport_hash(transport)
                record["transport_elapsed_seconds"] = transport.get("elapsed_seconds")
                record["usage"] = {key: response.get(key) for key in ("prompt_eval_count", "eval_count", "total_duration")}
                if response.get("done_reason") == "length":
                    record.update(status="length_abort", error_type="OutputLimit")
                else:
                    try:
                        record.update(status="valid", parsed=_classify(request, raw))
                    except (ValueError, TypeError, KeyError):
                        record.update(status="invalid_format", error_type="ResponseContract")
            except Exception as exc:
                record.update(status="transport_error", error_type=type(exc).__name__)
                record["retry_allowed"] = transient_transport(exc)
                transport_path = path / "calls.jsonl"
                if transport_path.exists():
                    transport = _last_transport_record(transport_path)
                    messages = transport.get("messages", [])
                    digest = _transport_hash(transport)
                    if (messages and messages[-1].get("content") == request["prompt"]
                            and digest not in known_transport_hashes):
                        record["transport_call_sha256"] = digest
                        raw = transport.get("response", {}).get("response")
                        if isinstance(raw, str):
                            record["raw_response"] = raw
                        record["done_reason"] = transport.get("response", {}).get("done_reason")
                if isinstance(exc, ValueError) and str(exc).startswith("Full request exceeds local context"):
                    record["error_code"] = "context_preflight"
            record["elapsed_seconds"] = time.perf_counter() - started
            _append(destination, record)
            existing[record["request_id"]] = record
            known_transport_hashes.add(record.get("transport_call_sha256"))
    finally:
        if runtime is not None:
            runtime.close()
            if model == JUDGE:
                request_json("/api/generate", {"model": runtime.name, "keep_alive": 0})
    return [existing[request["request_id"]] for request in requests]


def _requests(path, requests, model):
    """One immutable first attempt plus at most one identical technical retry.

    Each attempt has its own append-only raw and response ledger. Recovery runs
    before deciding whether to retry, so a crash cannot reset the attempt budget.
    """
    first = _requests_once(path, requests, model)
    eligible = {entry["request_id"] for entry in first
                if entry["status"] in ("invalid_format", "length_abort")
                or (entry["status"] == "transport_error" and entry.get("retry_allowed") is True)}
    second = _requests_once(path / "technical_retry_1",
                            [r for r in requests if r["request_id"] in eligible], model) if eligible else []
    retry_by_id = {entry["request_id"]: entry for entry in second}
    finals = []
    for entry in first:
        attempts = [entry]
        if entry["request_id"] in retry_by_id:
            attempts.append(retry_by_id[entry["request_id"]])
        final = dict(attempts[-1])
        final.update(first_status=entry["status"], final_status=final["status"],
                     technical_retry_count=len(attempts) - 1, attempts=attempts)
        finals.append(final)
    target = path / "final_responses.json"
    if target.exists():
        if json.loads(target.read_text(encoding="utf-8")) != finals:
            raise ValueError("Immutable sidecar final responses changed on resume")
    else:
        with target.open("x", encoding="utf-8") as stream:
            json.dump(finals, stream, ensure_ascii=False, indent=2, allow_nan=False)
    return finals


def _stage(summary, output, name, module, args):
    prior = next((stage for stage in summary["stages"] if stage["name"] == name), None)
    command = [sys.executable, "-X", "utf8", "-B", "-m", module, *map(str, args)]
    if prior is not None:
        if prior["command"] != command or prior["returncode"] != 0:
            raise ValueError(f"Cannot resume changed or failed native stage {name}")
        return False
    folder = Path(args[args.index("--output") + 1])
    if folder.exists():
        raise ValueError(f"Uncheckpointed native output exists: {folder}")
    started = time.perf_counter()
    try:
        result = subprocess.run(command, cwd=REPOSITORY, check=False)
        code = result.returncode
    except BaseException:
        raise
    finally:
        elapsed = time.perf_counter() - started
    summary["stages"].append({"name": name, "command": command,
                              "returncode": code, "elapsed_seconds": elapsed,
                              "finished_utc": _now()})
    write_json(output / "technical_summary.json", summary)
    if code:
        raise RuntimeError(f"Native stage {name} returned {code}")
    return True


def _unload_owned_judge():
    request_json("/api/generate", {"model": PROFILES[JUDGE]["ollama_model"], "keep_alive": 0})


def _construct(output, summary):
    _stage(summary, output, "input", "Experiments.strict_autoschemakg.local_pilot",
           ["prepare", "--output", output / "input"])
    runner = "Experiments.strict_autoschemakg.run"
    paths = []
    for number in range(1, 2):
        ident = f"c{number}"
        folder = output / ident
        _stage(summary, output, "construct-" + ident, runner,
               ["construct", "--data-directory", output / "input", "--filename-prefix", "lamport",
                "--model", CONSTRUCTOR, "--local-models", "--extraction-only", "--output", folder / "construct", "--execute"])
        extraction = _one_file(folder / "construct" / "kg_extraction", "*.json")
        concept = None
        paths.append((ident, folder, extraction, concept))
    return paths


def _native_judgments(output, summary, constructions):
    runner = "Experiments.strict_autoschemakg.run"
    for ident, folder, extraction, _ in constructions:
        was_recorded = any(stage["name"] == "triple-accuracy-" + ident for stage in summary["stages"])
        try:
            _stage(summary, output, "triple-accuracy-" + ident, runner,
                   ["triple-accuracy", "--input", extraction, "--output", folder / "triple_accuracy",
                    "--pilot-judge-repetitions", "3", "--repair-technical-retries", "--model", JUDGE, "--local-models", "--execute"])
        finally:
            if not was_recorded and (folder / "triple_accuracy").exists():
                _unload_owned_judge()


def _inventory(output, constructions, questions, questions_path):
    inventories = []
    for ident, folder, extraction, concept in constructions:
        items = artifacts.inventory_extraction(extraction, ident)
        concepts = artifacts.inventory_concepts(concept, ident, items) if concept else []
        record = artifacts.native_context_record(extraction, questions)
        target = folder / "inventory.json"
        inventory = {"construction_id": ident, "extraction_file": str(extraction),
                     "extraction_sha256": sha256(extraction), "concept_file": str(concept) if concept else None,
                     "concept_sha256": sha256(concept) if concept else None, "induction_enabled": concept is not None,
                     "questions_file": str(questions_path),
                     "questions_sha256": sha256(questions_path), "items": items, "concepts": concepts,
                     "native_context_record": record}
        _producer_calls(_records(folder / "construct" / "calls.jsonl"), inventory)
        if target.exists():
            old = json.loads(target.read_text(encoding="utf-8"))
            if old != inventory:
                raise ValueError("Immutable inventory changed on resume")
        else:
            with target.open("x", encoding="utf-8") as stream:
                json.dump(inventory, stream, ensure_ascii=False, indent=2, allow_nan=False)
                stream.write("\n")
        inventories.append((folder, inventory))
    return inventories


def _mcq_requests(inventory, *, mcq_parser_protocol=None):
    result = []
    for context_type in CONTEXTS:
        contexts = artifacts.context(inventory["native_context_record"], context_type)
        for question_index, question in enumerate(inventory["native_context_record"]["mcq_list"]):
            for repeat in range(1, 4):
                # Fixed, outcome-independent alternation of paired ordering.
                order = ("ad", "ae") if (question_index + repeat + CONTEXTS.index(context_type)) % 2 else ("ae", "ad")
                for order_index, variant in enumerate(order):
                    request = {"request_id": f"{inventory['construction_id']}:mcq:{context_type}:q{question_index+1}:r{repeat}:{variant}",
                                   "kind": "mcq", "variant": variant,
                                   "item_ids": [f"{inventory['construction_id']}:q{question_index+1}"],
                                   "context_type": context_type, "repeat": repeat,
                                   "pair_order": order_index,
                                   "prompt": measure.answer_prompt(question, contexts, variant)}
                    if mcq_parser_protocol is not None:
                        from .mcq_answer_bridge import PROTOCOL, validate_visible_options
                        if mcq_parser_protocol != PROTOCOL:
                            raise ValueError("Unknown MCQ parser protocol")
                        request["mcq_parser_protocol"] = mcq_parser_protocol
                        request["visible_options"] = list(question["options"]) + (
                            [measure.E_RULE.splitlines()[0]] if variant == "ae" else [])
                        validate_visible_options(request["visible_options"], variant)
                    result.append(request)
    return result


def _producer_calls(construction_calls, inventory):
    prefixes = {"entity": "Given a passage, summarize all the important entities",
                "event": "Please analyze and summarize the participation relations",
                "relation": "Please analyze and summarize the relationships between the events"}
    extraction = {}
    for category, prefix in prefixes.items():
        matches = [(index + 1, call) for index, call in enumerate(construction_calls)
                   if len(call.get("messages", [])) > 1
                   and call["messages"][1]["content"].startswith(prefix)
                   and _transport_valid(call, CONSTRUCTOR)]
        if "items" in inventory and "extraction_file" in inventory:
            import json_repair
            expected = [item["value"] for item in inventory["items"] if item["category"] == category]
            matches = [(index, call) for index, call in matches
                       if json_repair.loads(call["response"]["response"].split("</think>")[-1].strip()) == expected]
        if len(matches) != 1:
            raise ValueError(f"Missing or ambiguous native {category} extraction producer")
        extraction[category] = matches
    concepts = {}
    used = {index for group in extraction.values() for index, _ in group}
    concept_intro = {"event": "I will give you an EVENT.",
                     "entity": "I will give you an ENTITY.",
                     "relation": "I will give you an RELATION."}
    for item in inventory["concepts"]:
        row = item["csv_row"]
        if row in concepts:
            continue
        # Match native prompt target and concept_generation.py:98,249 CSV
        # projection only. Context/examples never identify the target.
        def target(call):
            prompt = call["messages"][1]["content"]
            if not prompt.startswith(concept_intro[item["category"]]):
                return None
            matches = re.findall(r"(?m)^\s*" + item["category"].upper()
                                 + r": ([^\r\n]*)$", prompt)
            return matches[-1] if matches else None

        candidates = [(index + 1, call) for index, call in enumerate(construction_calls)
                      if index + 1 not in used and len(call.get("messages", [])) > 1
                      and _transport_valid(call, CONSTRUCTOR)
                      and ", ".join(part.strip().lower() for part in
                                    call["response"]["response"].split(",")) == item["conceptualized_node_raw"]
                      and target(call) == item["object"]]
        if len(candidates) != 1:
            raise ValueError(f"Missing or ambiguous concept producer for CSV row {row}")
        concepts[row] = candidates
    return extraction, concepts


def _native_call_index(construction_id, calls, csv_path, declared_completed_draws=None):
    """Link draws only when raw calls and all native CSV rows prove the schedule."""
    rows = []
    columns_ok = False
    if csv_path.is_file():
        with csv_path.open(encoding="utf-8-sig", newline="") as stream:
            reader = csv.DictReader(stream)
            columns_ok = tuple(reader.fieldnames or ()) == NATIVE_CSV_COLUMNS
            rows = list(reader)
    missing_values = 0
    for row in rows:
        for column in NATIVE_CSV_COLUMNS[1:]:
            try:
                if not math.isfinite(float(row.get(column, ""))):
                    missing_values += 1
            except (TypeError, ValueError):
                missing_values += 1
    entries = []
    for number, call in enumerate(calls, 1):
        messages = call.get("messages", [])
        prompt = messages[-1].get("content", "") if messages else ""
        stages = [index + 1 for index, marker in enumerate(NATIVE_PROMPT_MARKERS) if marker in prompt]
        response = call.get("response", {})
        transport_valid = _transport_valid(call, JUDGE) and response.get("done_reason") != "length"
        entries.append({"call_id": f"{construction_id}:triple-judgment:{number:05d}",
                        "repetition_id": None, "call_in_repetition": None,
                        "prompt_stage": stages[0] if len(stages) == 1 else None,
                        "transport_valid": transport_valid,
                        "raw_response": response.get("response"),
                        "done_reason": response.get("done_reason")})
    reasons = []
    if not columns_ok or len(rows) != 3 or any(row.get("i") != "0" for row in rows):
        reasons.append("native_csv_not_three_complete_single_passage_draws")
    if declared_completed_draws is not None and declared_completed_draws != len(rows):
        reasons.append("native_manifest_csv_draw_count_mismatch")
    logical = []
    expected_stage = 1
    for number, entry in enumerate(entries):
        if entry["prompt_stage"] != expected_stage:
            reasons.append("native_six_prompt_sequence_unverified")
            break
        entry["attempt_in_logical_call"] = 1 + sum(
            e.get("logical_call_number") == len(logical) + 1 for e in entries[:number])
        entry["logical_call_number"] = len(logical) + 1
        # Native response accepts length-completed strings; count the physical
        # completion but retain its technical invalidity separately.
        if _transport_valid(calls[number], JUDGE):
            logical.append(number)
            expected_stage = len(logical) % 6 + 1
    if len(logical) != 18:
        reasons.append("logical_call_count_not_18")
    if not reasons:
        for entry in entries:
            number = entry["logical_call_number"] - 1
            entry["repetition_id"] = f"{construction_id}:triple-repeat:{number//6+1}"
            entry["call_in_repetition"] = number % 6 + 1
    return {"construction_id": construction_id, "repeat_linkage_verified": not reasons,
            "gap_reasons": reasons, "raw_call_count": len(calls),
            "logical_final_call_indices": [index + 1 for index in logical] if not reasons else [],
            "metric_values_valid": missing_values == 0,
            "logical_transport_valid": not reasons and all(entries[i]["transport_valid"] for i in logical),
            "completed_draws": len(rows), "missing_csv_values": missing_values,
            "call_index": entries}


def _confidence_requests(inventory, construction_calls, triple_calls, native_index, mcq_results):
    nemotron_items = []
    qwen = []
    extraction_producers, concept_producers = _producer_calls(construction_calls, inventory)
    for item in inventory["items"]:
        ident = item["occurrence_id"]
        category = "event" if item["category"] == "event_entity_link" else item["category"]
        producers = extraction_producers[category]
        original_input = [call["messages"] for _, call in producers]
        original_response = [call["response"]["response"] for _, call in producers]
        nemotron_items.append({"id": ident, "event": "extraction", "original_input": original_input,
                               "original_response": original_response,
                               "producer_call_ids": [index for index, _ in producers],
                               "focal_stored_item": item["value"]})
    for item in inventory["concepts"]:
        ident = item["id"]
        producers = concept_producers[item["csv_row"]]
        nemotron_items.append({"id": ident, "event": "induction",
                               "original_input": [call["messages"] for _, call in producers],
                               "original_response": [call["response"]["response"] for _, call in producers],
                               "producer_call_ids": [index for index, _ in producers],
                               "focal_stored_item": {
                                   "object": item["object"], "concept": item["concept"],
                                   "csv_row": item["csv_row"]}})
    batches = []
    for item in nemotron_items:
        if (not batches or len(batches[-1]) == CONFIDENCE_BATCH
                or batches[-1][0]["producer_call_ids"] != item["producer_call_ids"]):
            batches.append([])
        batches[-1].append(item)
    nemotron = []
    for index, batch in enumerate(batches):
        nemotron.append({"request_id": f"{inventory['construction_id']}:nemotron-confidence:{index:05d}",
                         "kind": "confidence", "item_ids": [x["id"] for x in batch],
                         "prompt": measure.confidence_batch_prompt(batch)})
    final_indices = native_index.get("logical_final_call_indices", list(range(1, len(triple_calls) + 1)))
    for index in final_indices:
        call = triple_calls[index - 1]
        ident = f"{inventory['construction_id']}:triple-judgment:{index:05d}"
        qwen.append({"request_id": ident + ":confidence", "kind": "confidence", "item_ids": [ident],
                     "prompt": measure.confidence_prompt(ident, "native_triple_judgment",
                         call.get("messages"), call.get("response", {}).get("response")),
                     **({"skip_reason": "invalid_native_judgment_transport"}
                        if not native_index["call_index"][index - 1]["transport_valid"] else {})})
    valid_mcq = [entry for entry in mcq_results if entry["status"] == "valid"]
    for entry in mcq_results:
        if entry["status"] != "valid":
            ident = entry["request_id"]
            qwen.append({"request_id": ident + ":confidence", "kind": "confidence", "item_ids": [ident],
                         "prompt": "not sent: invalid_mcq_answer:" + ident,
                         "skip_reason": "invalid_mcq_answer"})
    for start in range(0, len(valid_mcq), MCQ_CONFIDENCE_BATCH):
        group = valid_mcq[start:start + MCQ_CONFIDENCE_BATCH]
        batch = [{"id": entry["request_id"],
                  "event": "mcq_abstention" if entry["parsed"]["answer"] == "E" else "mcq_answer",
                  "original_input": entry["original_prompt"],
                  "original_response": entry.get("raw_response"),
                  "focal_stored_item": {"selected_letter": entry["parsed"]["answer"]}}
                 for entry in group]
        qwen.append({"request_id": f"{inventory['construction_id']}:mcq-confidence:{start//MCQ_CONFIDENCE_BATCH:05d}",
                     "kind": "confidence", "item_ids": [x["id"] for x in batch],
                     "prompt": measure.confidence_batch_prompt(batch)})
    return nemotron, qwen


def _collect(output, inventories):
    counts = {"expected": {}, "present": {}, "artifact_hashes": {}, "native_details": {},
              "invalid_format": 0, "transport_error": 0, "length_abort": 0,
              "missing_dependency": 0, "sidecar_attempts": {}}
    for folder, inventory in inventories:
        ident = inventory["construction_id"]
        mcq_requests = _mcq_requests(inventory)
        mcq = _requests(folder / "mcq_answers", mcq_requests, JUDGE)
        # The checkpoint stores request hash, while prompts are regenerated from
        # immutable inventories. Attach them only in-memory for post-hoc queries.
        mcq_by_id = {x["request_id"]: x for x in mcq_requests}
        for entry in mcq:
            entry["original_prompt"] = mcq_by_id[entry["request_id"]]["prompt"]
        calls = _records(folder / "triple_accuracy" / "calls.jsonl")
        native_manifest = json.loads((folder / "triple_accuracy" / "manifest.json").read_text(encoding="utf-8"))
        csv_path = Path(native_manifest["result"]["output_file"]).resolve()
        if not csv_path.is_relative_to((folder / "triple_accuracy").resolve()):
            raise ValueError("Native CSV path escapes its stage folder")
        native_index = _native_call_index(ident, calls, csv_path,
                                          native_manifest["result"].get("completed_draws"))
        native_index["calls_file_sha256"] = sha256(folder / "triple_accuracy" / "calls.jsonl")
        native_index["csv_file_sha256"] = sha256(csv_path) if csv_path.is_file() else None
        native_index_path = folder / "native_judgment_index.json"
        if native_index_path.exists():
            if json.loads(native_index_path.read_text(encoding="utf-8")) != native_index:
                raise ValueError("Native judgment index changed on resume")
        else:
            with native_index_path.open("x", encoding="utf-8") as stream:
                json.dump(native_index, stream, ensure_ascii=False, indent=2, allow_nan=False)
                stream.write("\n")
        from .judgment_audit import audit_native_calls
        logical_indices = native_index.get("logical_final_call_indices", [])
        audit = audit_native_calls([calls[i - 1] for i in logical_indices], inventory)
        audit["physical_call_indices"] = logical_indices
        audit["native_calls_sha256"] = native_index["calls_file_sha256"]
        audit["logical_mapping_verified"] = native_index["repeat_linkage_verified"]
        audit_path = folder / "judgment_audit.json"
        if audit_path.exists():
            if json.loads(audit_path.read_text(encoding="utf-8")) != audit:
                raise ValueError("Immutable judgment audit changed on resume")
        else:
            with audit_path.open("x", encoding="utf-8") as stream:
                json.dump(audit, stream, ensure_ascii=False, indent=2, allow_nan=False)
        construction_calls = _records(folder / "construct" / "calls.jsonl")
        nemotron_conf, qwen_conf = _confidence_requests(inventory, construction_calls, calls,
                                                        native_index, mcq)
        ne = _requests(folder / "confidence_nemotron", nemotron_conf, CONSTRUCTOR)
        qw = _requests(folder / "confidence_qwen", qwen_conf, JUDGE)
        all_results = mcq + ne + qw
        counts["sidecar_attempts"][ident] = {
            "logical_requests": len(all_results),
            "physical_attempts": sum(len(entry.get("attempts", [entry])) for entry in all_results),
            "technical_retries": sum(entry.get("technical_retry_count", 0) for entry in all_results),
            "first_status_counts": {status: sum(entry.get("first_status", entry["status"]) == status
                                                for entry in all_results)
                                    for status in ("valid", "invalid_format", "length_abort", "transport_error", "missing_dependency")}}
        counts["expected"][ident] = {"mcq_answers": len(mcq_requests),
                                      "confidence_nemotron": sum(len(x["item_ids"]) for x in nemotron_conf),
                                      "confidence_qwen": sum(len(x["item_ids"]) for x in qwen_conf),
                                      "native_triple_calls": 18}
        counts["present"][ident] = {"mcq_answers": sum(x["status"] == "valid" for x in mcq),
                                     "confidence_nemotron": sum(len(x["item_ids"]) for x in ne if x["status"] == "valid"),
                                     "confidence_qwen": sum(len(x["item_ids"]) for x in qw if x["status"] == "valid"),
                                     "native_triple_calls": 18 if native_index["repeat_linkage_verified"] and native_index.get("logical_transport_valid", True) else 0}
        counts["native_details"][ident] = {key: native_index[key] for key in
                                            ("repeat_linkage_verified", "gap_reasons", "raw_call_count",
                                             "completed_draws", "missing_csv_values")}
        counts["native_details"][ident]["judgment_audit_schedule_valid"] = audit.get("schedule_valid", False)
        counts["native_details"][ident]["judgment_audit_invalid_calls"] = sum(
            not category[kind]["valid"] for repetition in audit.get("repetitions", [])
            for name, category in repetition.items() if isinstance(category, dict)
            for kind in ("more", "incorrect"))
        construction_attempts = _records(folder / "construct" / "calls.jsonl")
        counts["native_details"][ident]["extraction_length_aborts"] = sum(
            c.get("response", {}).get("done_reason") == "length" for c in construction_attempts)
        counts["length_abort"] += sum(x.get("response", {}).get("done_reason") == "length" for x in calls)
        counts["transport_error"] += sum("transport_error" in x for x in calls)
        for status in ("invalid_format", "transport_error", "length_abort", "missing_dependency"):
            counts[status] += sum(x["status"] == status for x in all_results)
        files = [folder / "inventory.json", native_index_path, audit_path,
                 folder / "construct" / "manifest.json",
                 folder / "construct" / "calls.jsonl",
                 folder / "triple_accuracy" / "manifest.json",
                 folder / "triple_accuracy" / "calls.jsonl"]
        files += [folder / subdir / name
                  for subdir in ("mcq_answers", "confidence_nemotron", "confidence_qwen")
                  for name in ("responses.jsonl", "calls.jsonl", "local_runtime.json", "final_responses.json",
                               "technical_retry_1/responses.jsonl", "technical_retry_1/calls.jsonl", "technical_retry_1/local_runtime.json")]
        counts["artifact_hashes"][ident] = {str(path.relative_to(folder)): sha256(path)
                                           for path in files if path.is_file()}
    return counts


def preflight(output, questions_path):
    source = verify_source(DEFAULT_SOURCE)
    questions = artifacts.load_questions(questions_path)
    revised, question_provenance = frozen_questions.prepare(questions_path, ARTICLE)
    return {"variant": "extended_local_lamport_pilot_repair_v1", "source": source,
            "article_path": str(ARTICLE), "article_sha256": sha256(ARTICLE),
            "questions_path": str(questions_path), "questions_sha256": sha256(questions_path),
            "question_version": question_provenance,
            "revised_questions_sha256": artifacts.digest(revised),
            "retry_policy": {"sidecar_additional_attempts": 1,
                             "eligible": ["invalid_format", "length_abort", "transient_transport"],
                             "native_retries": "native ceilings unchanged, judge transient-only opt-in, no outer retries",
                             "outcome_based_retries": False},
            "question_count": len(questions), "constructions": 1,
            "construction_mode": "extraction_only", "induction_enabled": False, "graph_build_enabled": False,
            "native_triple_repetitions_per_construction": 3,
            "mcq_repetitions_per_question_context_variant": 3,
            "confidence_batch_size": CONFIDENCE_BATCH,
            "mcq_confidence_batch_size": MCQ_CONFIDENCE_BATCH,
            "model_profiles": {name: {"ollama_digest": PROFILES[name]["ollama_digest"],
                                      "tokenizer_revision": PROFILES[name]["revision"]}
                               for name in (CONSTRUCTOR, JUDGE)},
            "output_tokens": OUTPUT_TOKENS, "analysis_performed": False,
            "adapter_sha256": {path.name: sha256(path) for path in
                               sorted(Path(__file__).parent.glob("*.py"))},
            "output": str(output.resolve())}


def execute(output, pre):
    output = Path(output).resolve()
    checkpoint = output / "technical_summary.json"
    if output.exists():
        if not checkpoint.is_file():
            raise ValueError("Existing output has no resumable technical checkpoint")
        summary = json.loads(checkpoint.read_text(encoding="utf-8"))
        if summary.get("preflight") != pre:
            raise ValueError("Resume inputs or pinned source differ from checkpoint")
    else:
        new_output(output)
        summary = {"status": "running", "preflight": pre, "stages": [],
                   "analysis_performed": False, "started_utc": _now()}
        write_json(checkpoint, summary)
    try:
        constructions = _construct(output, summary)
        revised, provenance = frozen_questions.prepare(Path(pre["questions_path"]), ARTICLE)
        if provenance != pre["question_version"] or artifacts.digest(revised) != pre["revised_questions_sha256"]:
            raise ValueError("Question provenance changed after preflight")
        questions_path = frozen_questions.persist(output / "frozen_questions", revised, provenance)
        questions = artifacts.load_questions(questions_path)
        inventories = _inventory(output, constructions, questions, questions_path)
        _native_judgments(output, summary, constructions)
        counts = _collect(output, inventories)
        if sha256(ARTICLE) != pre["article_sha256"] or sha256(Path(pre["questions_path"])) != pre["questions_sha256"]:
            raise ValueError("Source article or fixed questions changed during collection")
        verify_source(DEFAULT_SOURCE)
        summary["technical_counts"] = counts
        complete = all(counts["expected"][ident] == counts["present"][ident]
                       for ident in ("c1",))
        complete = complete and all(not detail["missing_csv_values"]
                                    and detail["judgment_audit_schedule_valid"]
                                    and not detail["judgment_audit_invalid_calls"]
                                    and not detail["extraction_length_aborts"]
                                    for detail in counts["native_details"].values())
        summary["status"] = "technically_complete_uninterpreted" if complete else "technical_gaps_uninterpreted"
        return 0 if complete else 2
    except BaseException as exc:
        summary.update(status="failed_checkpoint", error_type=type(exc).__name__)
        raise
    finally:
        summary["finished_utc"] = _now()
        write_json(checkpoint, summary)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--questions-input", type=Path, default=QUESTIONS)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--reliability-v2", action="store_true",
                        help="Explicit schema/ID protocol variant with at most 10 technical retries (11 total attempts)")
    parser.add_argument("--capability-check", action="store_true",
                        help="With --reliability-v2 --execute, run only two technical decoder probes")
    parser.add_argument("--include-mcqs", action="store_true",
                        help="With --reliability-v2, enable the historical full MCQ evaluation scope")
    args = parser.parse_args(argv)
    if args.include_mcqs and not args.reliability_v2:
        parser.error("--include-mcqs requires --reliability-v2")
    if args.include_mcqs and args.capability_check:
        parser.error("--include-mcqs cannot be combined with --capability-check")
    if args.capability_check and not (args.reliability_v2 and args.execute):
        parser.error("--capability-check requires --reliability-v2 --execute")
    if args.reliability_v2:
        from . import reliability_v2
        pre = reliability_v2.preflight(args.output, args.questions_input.resolve(), include_mcqs=args.include_mcqs)
    else:
        pre = preflight(args.output, args.questions_input.resolve())
    if not args.execute:
        print(json.dumps(pre, ensure_ascii=False, indent=2))
        return 0
    if request_json("/api/ps").get("models"):
        raise RuntimeError("Ollama has a loaded model; extended pilot will not take over an existing model")
    if args.capability_check:
        return reliability_v2.capability_check(args.output)
    return (reliability_v2.execute(args.output, pre) if args.reliability_v2 else execute(args.output, pre))


if __name__ == "__main__":
    sys.dont_write_bytecode = True
    raise SystemExit(main())
