"""Source-only CPU freeze of a fresh, blinded AS extraction precollection.

This is not confirmation dispatch approval. It does not dispatch, instantiate a
provider, load credentials or inspect outcomes/reference annotations. Each draw
has a fresh source construction. Original SDK chunking, loader batches, prompt
order, schemas and parser are pinned. Schema/graph tails are deliberately left
for the later matched comparison. A separate OS process must execute the native
worker; reviewer engines/Core-origin imports may not share that process.
"""
from __future__ import annotations

from copy import deepcopy
import ast
from dataclasses import asdict
from hashlib import sha256
from pathlib import Path

from Experiments.fair_comparison_oct23_v1 import baseline
from Experiments.strict_autoschemakg.contract import parse_json, verify_source
from Tools.experiments.fair_tail_oct23_v1 import runtime


PROTOCOL = "blind-original-AS-extraction-precollection:oct23-v1"
DRAWS = ("draw_1", "draw_2", "draw_3")
BASELINE_CODE_SHA256 = "2af3e01d685e6bf3ee85403e0429ef06ed8b67ad55b27cafce2c3bdaddee30d6"


def _require(condition, message):
    if not condition:
        raise ValueError(message)


def pin(path, expected_sha256=None):
    path = Path(path).resolve(strict=True)
    _require(path.is_file(), "Regular explicitly named input required")
    raw = path.read_bytes()
    digest = sha256(raw).hexdigest()
    _require(expected_sha256 is None or digest == expected_sha256, "Bound input SHA256 differs")
    return {"path": str(path), "bytes": len(raw), "sha256": digest}


def source_payload(path, expected_sha256):
    """Only the explicitly allowed constructor JSON and its plain sources."""
    evidence = pin(path, expected_sha256)
    rows = parse_json(Path(evidence["path"]).read_bytes())
    _require(type(rows) is list and all(type(row) is dict and set(row) == {"id", "text", "sha256"}
        for row in rows), "Source-only id/text/sha256 inventory required; no extra fields")
    return baseline._sources(rows), evidence


def verify_source_manifest(path, sources):
    """Read no sibling provenance, annotation, reference or outcome files."""
    evidence = pin(path)
    manifest = parse_json(Path(evidence["path"]).read_bytes())
    _require(manifest.get("role") == "source_only_candidate_confirmation"
        and manifest.get("construction_dispatch_allowed") is False,
        "Original closed source-only confirmation manifest required")
    cases = manifest.get("cases")
    _require(type(cases) is list and [case["id"] for case in cases] == [row["id"] for row in sources],
        "Original complete source order must agree with constructor payload")
    pins = []
    for case, source in zip(cases, sources, strict=True):
        _require(len(case["documents"]) == 1, "This bounded precollection expects one original document per case")
        doc = case["documents"][0]
        candidate = (Path(evidence["path"]).parent / doc["path"]).resolve(strict=True)
        allowed = (Path(evidence["path"]).parent / "source-only-documents").resolve(strict=True)
        _require(candidate.is_relative_to(allowed), "Only named source-only documents may be opened")
        entry = pin(candidate, doc["sha256"])
        _require(Path(entry["path"]).read_bytes() == source["text"].encode("utf8")
            and source["sha256"] == entry["sha256"], "Original source bytes differ from constructor payload")
        pins.append(entry)
    return evidence, pins


def policy(max_calls=3):
    return baseline.ExecutionPolicy(model=runtime.MODEL, context_limit=None,
        wire_parameters=deepcopy(runtime.PARAMETERS), timeout_seconds=runtime.TIMEOUT,
        max_calls=max_calls, chunk_size=8192, chunk_overlap=0, batch_size=3,
        native_output_limit=8192, remove_doc_spaces=False)


def _runtime_code_pins():
    """Pin declared reusable wire code without importing reviewer/Core clients."""
    reader = pin(runtime.READER, runtime.READER_SHA)
    tree = ast.parse(Path(reader["path"]).read_bytes())
    declared = {}
    for node in tree.body:
        if isinstance(node, ast.Assign) and isinstance(node.value, ast.Call):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id in {"ORIGINAL", "BRIDGE"}:
                    declared[target.id] = Path(ast.literal_eval(node.value.args[0]))
    _require(set(declared) == {"ORIGINAL", "BRIDGE"}, "Original runtime must declare both existing wire helpers")
    pins = [reader, *(pin(path) for path in declared.values())]
    bridge_tree = ast.parse(declared["BRIDGE"].read_bytes())
    declaration = next(node for node in bridge_tree.body if isinstance(node, ast.Assign)
        and any(isinstance(target, ast.Name) and target.id == "SOURCE_PINS" for target in node.targets))
    for relative, wanted in ast.literal_eval(declaration.value).items():
        pins.append(pin(baseline.ROOT / relative, wanted))
    for path, wanted in baseline._code_pins(runtime).items():
        pins.append(pin(path, wanted))
    return list({entry["path"]: entry for entry in pins}.values())


def _native_loader(source, *, sdk_source):
    """Call the original SDK processor/loader, never a copied chunk algorithm."""
    with baseline.construction.verified_source_imports(sdk_source):
        native = baseline.construction._load_native(sdk_source)
        from atlas_rag.kg_construction.triple_extraction import DatasetProcessor, CustomDataLoader
        config = native.ProcessingConfig(model_path=runtime.MODEL, data_directory="source-only-input",
            filename_pattern="source", output_directory="not-created-cpu-only",
            batch_size_triple=3, max_workers=1, max_new_tokens=8192,
            remove_doc_spaces=False, chunk_size=8192, chunk_overlap=0, debug_mode=False,
            benchmark=False, resume_from=0, deduplicate_text=False,
            total_shards_triple=1, current_shard_triple=0,
            total_shards_concept=1, current_shard_concept=0)
        # Exactly the input metadata default used by baseline.construct.
        model = type("NoInferenceMetadata", (), {"model_name": runtime.MODEL})()
        extractor = native.KnowledgeGraphExtractor(model=model, config=config)
        sample = {"id": source["id"], "text": source["text"],
                  "metadata": deepcopy(source.get("metadata", {"lang": "en"}))}
        processor = DatasetProcessor(config, extractor.prompt_instructions, extractor.result_schema)
        loader = CustomDataLoader([sample], processor, extractor.prompt_instructions, extractor.result_schema)
        chunks = deepcopy(loader.processed_data)
        _require(bool(chunks) and all(chunk["id"] == source["id"] for chunk in chunks),
            "Original loader must cover this source, without silent language filtering")
        calls = []
        for batch_index, (messages, ids, texts, metadata) in enumerate(loader):
            for category, batch_messages in messages.items():
                _require(len(batch_messages) == len(ids) == len(texts) == len(metadata),
                    "Original batch arrays differ")
                for index, message in enumerate(batch_messages):
                    calls.append({"batch_index": batch_index, "within_category_batch_index": index,
                        "category": category, "source_id": ids[index],
                        "chunk_id": chunks[batch_index * config.batch_size_triple + index]["chunk_id"],
                        "chunk_text_sha256": sha256(texts[index].encode("utf8")).hexdigest(),
                        "messages": deepcopy(message), "schema": deepcopy(extractor.result_schema[category])})
        _require(len(calls) == 3 * len(chunks), "Every SDK chunk needs its original EE/EV/VV calls")
        return {"chunks": chunks, "calls": calls, "processing_config": asdict(config),
            "prompt_template_sha256": baseline.digest(extractor.prompt_instructions),
            "native_schema_sha256": baseline.digest(extractor.result_schema)}


def prepare_plan(sources, *, source_pins, sdk_source=baseline.DEFAULT_SOURCE, loader=None):
    """Return a frozen preparatory plan. No execution/approval path exists here."""
    sources = baseline._sources(sources)
    _require(len(sources) > 0, "Nonempty original source payload required")
    _require(type(source_pins) is list and source_pins, "Exact constructor payload must be the first input pin")
    original_sources, _ = source_payload(source_pins[0]["path"], source_pins[0]["sha256"])
    _require(baseline.canonical(original_sources) == baseline.canonical(sources),
        "Precollection sources differ from the pinned original source-only constructor payload")
    baseline_pin = pin(baseline.__file__, BASELINE_CODE_SHA256)
    original = verify_source(sdk_source)
    original_protocol = Path(baseline.__file__).with_name("protocol_v1.json")
    protocol_pin = pin(original_protocol)
    protocol = parse_json(original_protocol.read_bytes())
    _require(protocol["confirmation"]["dispatch_allowed"] is False,
        "Old confirmation dispatch gate must remain closed")
    for entry in source_pins:
        _require(pin(entry["path"]) == entry, "Original source-only input changed")
    loader = loader or (lambda source: _native_loader(source, sdk_source=sdk_source))
    prepared = []
    for source in sources:
        data = loader(deepcopy(source))
        _require(len(data["calls"]) == 3 * len(data["chunks"]) and data["chunks"],
            "Complete native loader chunks and calls required")
        prepared.append((source, data))
    jobs, posts = [], []
    for draw in DRAWS:
        for source_index, (source, data) in enumerate(prepared):
            job_id = draw + ":source_" + str(source_index + 1).zfill(2)
            job_calls = []
            for local_index, call in enumerate(data["calls"]):
                body = {**deepcopy(runtime.PARAMETERS), "messages": deepcopy(call["messages"])}
                item = {**deepcopy(call), "physical_call_id": job_id + ":call_" + str(local_index + 1).zfill(4),
                    "global_index": len(posts), "local_index": local_index,
                    "payload": body, "payload_sha256": baseline.digest(body),
                    "HTTP_timeout_seconds": 300, "maximum_physical_POSTs": 1,
                    "transport_retries": 0, "native_validation_regenerations": 0}
                job_calls.append(item)
                posts.append({"physical_call_id": item["physical_call_id"], "payload_sha256": item["payload_sha256"]})
            jobs.append({"job_id": job_id, "draw_id": draw, "source_index": source_index,
                "source_id": source["id"], "source_sha256": source["sha256"],
                "original_chunks": deepcopy(data["chunks"]), "source_only_input": deepcopy(source),
                "processing_config": deepcopy(data["processing_config"]),
                "native_prompt_template_sha256": data["prompt_template_sha256"],
                "native_schema_sha256": data["native_schema_sha256"],
                "execution_policy": asdict(policy(max_calls=len(job_calls))), "calls": job_calls})
    code = [pin(__file__), baseline_pin, pin(runtime.__file__), *_runtime_code_pins()]
    code = list({entry["path"]:entry for entry in code}.values())
    value = {"protocol": PROTOCOL, "phase": "source_only_baseline_precollection_prepared_not_dispatched",
        "dispatch_allowed": False, "root_review_of_exact_plan_required_before_dispatch": True,
        "original_confirmation_gate": protocol_pin,
        "original_confirmation_dispatch_allowed_unchanged": False,
        "scope": "fresh original AS extraction only; schema/graph suffix later matched with the frozen candidate",
        "source_pins": deepcopy(source_pins), "sources": len(sources), "draw_order": list(DRAWS),
        "source_order": [source["id"] for source in sources], "jobs": jobs,
        "planned_source_draw_constructions": len(jobs), "planned_physical_extraction_POSTs": len(posts),
        "planned_maximum_completion_tokens": len(posts) * 8192,
        "serial_sum_of_per_POST_HTTP_timeout_seconds_not_duration_estimate": len(posts) * 300,
        "native_chunks_per_draw": sum(len(data["chunks"]) for _, data in prepared),
        "physical_order": posts, "policy": asdict(policy(max_calls=max(len(job["calls"]) for job in jobs))), "code_pins": code,
        "original_sdk_verification": original, "new_model_calls": 0,
        "execution_contract": {"worker_process": "separate fresh OS process; original Main SDK imports only",
            "python_utf8_mode_required": True, "worker_python_arguments": ["-X", "utf8"],
            "reviewer_engine_or_sibling_Core_in_worker": False, "sys_modules_origin_hacks": False,
            "reuse_old_outputs_or_cross_draw_request_cache": False,
            "one_physical_post_per_predeclared_call": True,
            "native_parser": "unchanged original validate_output/fix_triple_extraction_response plus OutputParser",
            "parser_rejection": "stop; never regenerate or invent [] to hide failure",
            "transport_or_unknown_execution": "stop entire precollection; no replay or automatic restart",
            "schema_or_graph_generation_in_this_phase": False},
        "blinding": {"rule_not_filesystem_security_guarantee": True,
            "allowed_constructor_inputs": "only supplied source-only payload and named plain source files",
            "reference_annotation_files_opened": False,
            "result_values_unread_until_candidate_freeze": True,
            "before_freeze_reporting": "execution counts, statuses and cryptographic pins only",
            "outputs_shared_with_candidate_or_judge_developers_before_freeze": False,
            "this_precollection_owner_loses_candidate_Judge_and_role_development_for_these_sources": True,
            "baseline_independent_of_unfrozen_candidate_design": True}}
    value["temperature_policy"] = "Prospectively fixed 0.7 primary comparison; no optimality claim or outcome-driven temperature change"
    return {**value, "plan_sha256": baseline.digest(value)}


def next_dispatch_index(plan, receipts):
    """CPU guard over technical status only; never inspect response values.

    This does not approve a dispatch. A real worker must additionally receive
    root approval for the exact plan and preserve its one-POST wire contract.
    """
    _require(plan.get("protocol") == PROTOCOL and plan.get("plan_sha256") == baseline.digest(
        {key: value for key, value in plan.items() if key != "plan_sha256"}), "Frozen plan differs")
    _require(type(receipts) is list and len(receipts) <= len(plan["physical_order"]), "Ordered receipt prefix required")
    for index, receipt in enumerate(receipts):
        expected = plan["physical_order"][index]
        _require(set(receipt) == {"physical_call_id", "payload_sha256", "POST_attempts", "unknown_execution", "status"},
            "Only bound technical receipt headers are permitted")
        _require(all(receipt[key] == expected[key] for key in expected), "Call order or payload binding differs")
        _require(type(receipt["POST_attempts"]) is int and receipt["POST_attempts"] == 1,
            "Exactly one physical POST per predeclared call required")
        _require(receipt["unknown_execution"] is False and receipt["status"] == "completed",
            "Unknown or failed call stops all continuation; no replay")
    return len(receipts) if len(receipts) < len(plan["physical_order"]) else None
