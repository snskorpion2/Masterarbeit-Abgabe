"""Matched AutoSchemaKG execution, preserving the pinned five native stages.

This module owns orchestration and evidence, never extraction/schema semantics.
The injected runtime owns actual HTTP policy. Native kwargs and declared wire
parameters are deliberately separate: matching a provider is a new condition.
Imports neither read credentials nor contact a provider.
"""
from __future__ import annotations

from contextlib import nullcontext
from collections import Counter
from copy import deepcopy
import csv
from dataclasses import asdict, dataclass
import hashlib
import json
from pathlib import Path
import sys
from threading import Lock
from types import SimpleNamespace

from Experiments.src.file_io import sha256_file, sha256_text, write_json_atomic
from Experiments.strict_autoschemakg import construction

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SOURCE = ROOT / "Tools/ReferenceRepos/benchmark_autoschemakg_original"
PROTOCOL = "matched-native-autoschemakg-oct23-v1"
STAGES = ("run_extraction", "convert_json_to_csv", "generate_concept_csv_temp",
          "create_concept_csv", "convert_to_graphml")
FIELDS = ("entity_relation_dict", "event_entity_dict", "event_relation_dict")


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"), allow_nan=False).encode("utf-8")


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def _code_pins(runtime, extra=()):
    paths = [Path(__file__), *map(Path, extra)]
    for rel in ("Experiments/strict_autoschemakg/construction.py",
                "Experiments/strict_autoschemakg/contract.py",
                "Experiments/strict_autoschemakg/source_imports.py",
                "Tools/experiments/autoschema_ladder_oct14_v1/runner.py",
                "Tools/experiments/oneagent_roles_oct20_v1/native_luna_runtime_v3.py",
                "Tools/experiments/source_anchor_gap_oct20_v1/native_luna_v2.py",
                "Tools/experiments/source_anchor_gap_oct20_v1/run_study.py",
                "Tools/experiments/autoschema_ladder_oct14_v1/assertion_audit.py",
                "Tools/azure/probe.py", "Tools/azure/accounting.py",
                "Tools/azure/output_budget_probe_v2.py"):
        paths.append(ROOT / rel)
    module = sys.modules.get(type(runtime).__module__)
    if module is not None and getattr(module, "__file__", None):
        paths.append(Path(module.__file__))
    return {str(p): sha256_file(p) for p in paths}


class BaselineAbort(BaseException):
    """Do not let the native Exception-to-empty fallback swallow a failed run."""


@dataclass(frozen=True)
class ExecutionPolicy:
    model: str
    context_limit: int | None
    wire_parameters: dict
    timeout_seconds: int = 300
    max_calls: int = 12
    chunk_size: int = 8192
    chunk_overlap: int = 0
    batch_size: int = 3
    native_output_limit: int = 2048
    remove_doc_spaces: bool = False

    def __post_init__(self):
        for name in ("timeout_seconds", "max_calls", "chunk_size",
                     "batch_size", "native_output_limit"):
            if type(getattr(self, name)) is not int or getattr(self, name) <= 0:
                raise ValueError("Positive integer execution limits required")
        if (type(self.model) is not str or not self.model or type(self.wire_parameters) is not dict
                or self.wire_parameters.get("model") != self.model
                or "messages" in self.wire_parameters
                or type(self.remove_doc_spaces) is not bool
                or type(self.chunk_overlap) is not int
                or not 0 <= self.chunk_overlap < self.chunk_size):
            raise ValueError("Explicit matching model/wire/chunk policy required")
        cap = self.wire_parameters.get("max_completion_tokens", self.wire_parameters.get("max_tokens"))
        if (self.context_limit is not None and (type(self.context_limit) is not int or self.context_limit <= 0)):
            raise ValueError("Context is an explicit positive configured limit or unknown None")
        if type(cap) is not int or cap <= 0 or (self.context_limit is not None and cap >= self.context_limit):
            raise ValueError("Actual output cap must leave positive context for the prompt")
        canonical(self.wire_parameters)


def _sources(sources):
    if type(sources) is not list or not sources:
        raise ValueError("Ordered source-only documents required")
    result, ids = [], set()
    for row in sources:
        if (type(row) is not dict or not {"id", "text", "sha256"} <= set(row)
                or set(row) - {"id", "text", "sha256", "metadata"}
                or type(row["id"]) is not str or not row["id"] or row["id"] in ids
                or type(row["text"]) is not str or not row["text"]
                or row["sha256"] != sha256_text(row["text"])
                or type(row.get("metadata", {})) is not dict):
            raise ValueError("Unique complete source identities and matching UTF-8 hashes required")
        ids.add(row["id"])
        result.append(deepcopy(row))
    return result


class _ObservedRuntime:
    def __init__(self, runtime, output, policy, manifest):
        self.runtime, self.output, self.policy = runtime, output, policy
        self.requested_model = policy.model
        self.tokenizer = getattr(runtime, "tokenizer", None)
        self.metadata = deepcopy(getattr(runtime, "metadata", {}))
        self.metadata.update(backend=self.metadata.get("backend", "injected_runtime"),
                             matched_policy=asdict(policy))
        self.phase, self.abort_required, self.receipts = None, False, []
        self.call_limit = policy.max_calls
        self.manifest, self.lock = manifest, Lock()
        self.expected_prompts = {}
        self.before_generate = None

    def generate(self, messages, parameters):
        with self.lock:
            if self.before_generate is not None:
                callback, self.before_generate = self.before_generate, None
                try:
                    callback()
                except BaseException:
                    self.abort_required = True
                    raise BaselineAbort("Native roster preparation failed before dispatch") from None
            if digest(asdict(self.policy)) != self.manifest["policy_sha256"]:
                self.abort_required = True
                raise BaselineAbort("Bound execution policy changed before dispatch")
            if self.abort_required or getattr(self.runtime, "abort_required", False):
                raise BaselineAbort("Previous execution failed; no further dispatch")
            if len(self.receipts) >= self.call_limit:
                self.abort_required = True
                raise BaselineAbort("Explicit physical-call ceiling reached")
            index = len(self.receipts)
            folder = self.output / "observed_calls" / f"{index:05d}"
            payload = {**deepcopy(self.policy.wire_parameters), "messages": deepcopy(messages)}
            prompt_hash = digest(messages)
            record = {"ordinal": index, "phase": self.phase, "status": "not_dispatched",
                      "messages": deepcopy(messages), "prompt_sha256": prompt_hash,
                      "native_parameters": deepcopy(parameters),
                      "declared_wire_payload_sha256": digest(payload),
                      "declared_wire_parameters": deepcopy(self.policy.wire_parameters),
                      "source_candidates": deepcopy(self.expected_prompts.get(prompt_hash, [])),
                      "request_id": f"AS:{index:05d}:{digest(payload)}"}
            self.receipts.append(record)
            try:
                folder.mkdir(parents=True, exist_ok=False)
                if self.phase == "run_extraction" and not record["source_candidates"]:
                    raise ValueError("Native prompt differs from the prebound source-only loader")
                # Every dynamic concept prompt is sealed before invoking HTTP too.
                write_json_atomic(folder / "intent.json", record)
                write_json_atomic(folder / "declared-wire-request.json", payload)
                record["status"] = "dispatch_entered"
                write_json_atomic(folder / "dispatch_started.json", {
                    "request_id": record["request_id"], "wire_sha256": digest(payload),
                    "unsettled_execution_is_unknown": True})
                self.runtime.phase = self.phase
                text = self.runtime.generate(deepcopy(messages), deepcopy(parameters))
                if type(text) is not str or getattr(self.runtime, "abort_required", False):
                    raise ValueError("Complete native text response required")
                record.update(status="completed", raw_response=text,
                              raw_response_sha256=sha256_text(text))
                # Existing runtime receipts independently bind the actual wire.
                actual = getattr(self.runtime, "receipts", [])
                if actual:
                    record["runtime_receipt"] = deepcopy(actual[-1])
                request_file = self.output / "calls" / f"{index:05d}" / "request.json"
                if not request_file.is_file():
                    raise ValueError("Actual runtime request archive missing")
                raw_request = request_file.read_bytes()
                record["actual_wire_request_sha256"] = hashlib.sha256(raw_request).hexdigest()
                if canonical(json.loads(raw_request)) != canonical(payload):
                    raise ValueError("Actual runtime wire parameters differ from bound pair policy")
                return text
            except BaseException as error:
                self.abort_required = True
                record.update(status="aborted", error_class=type(error).__name__)
                actual = getattr(self.runtime, "receipts", [])
                if actual:
                    record["runtime_receipt"] = deepcopy(actual[-1])
                    if actual[-1].get("unknown_execution") is True:
                        record["status"] = "unknown_execution"
                raise BaselineAbort("Baseline request failed; no automatic resend") from None
            finally:
                try:
                    write_json_atomic(folder / "receipt.json", record)
                except BaseException:
                    self.abort_required = True
                    raise BaselineAbort("Baseline receipt storage failed; no further sends") from None


def construct(sources, runtime, output, *, policy, source=DEFAULT_SOURCE, native=None,
              native_tail_scope=None, complete_native_tail=False):
    """Execute all native batches/chunks and original schema/GraphML stages.

    runtime.generate(messages, native_kwargs) must preserve stopped text, journal
    its actual wire/usage, and halt unknown execution. policy declares the actual
    common backend settings, not sampling equivalence to Transformers defaults.
    An incomplete run retains its prefix and raises BaselineAbort. The function
    never resumes or silently shortens sources/concept nodes to fit a call cap.
    """
    sources = _sources(sources)
    if not isinstance(policy, ExecutionPolicy) or not callable(getattr(runtime, "generate", None)):
        raise ValueError("ExecutionPolicy and explicit injected text runtime required")
    if type(complete_native_tail) is not bool:
        raise ValueError("Explicit complete-native-tail execution flag required")
    tail_scope = None
    if native_tail_scope is not None:
        scope_path = Path(native_tail_scope)
        tail_scope = json.loads(scope_path.read_bytes())
        conditions = Path(__file__).with_name("pilot_conditions_v1.json")
        if (tail_scope.get("extension_id") != "as-fair-complete-native-tail-development-oct23-v1"
                or tail_scope.get("extends_condition_sha256") != sha256_file(conditions)):
            raise ValueError("Matching explicit native-tail extension required")
        condition = json.loads(conditions.read_bytes())
        source_manifest = Path(__file__).with_name(condition["sources_manifest"])
        admitted = [s for s in json.loads(source_manifest.read_bytes())["sources"]
                    if s["source_id"] == condition["full_pipeline_integration"]["source_id"]]
        if (len(sources) != 1 or len(admitted) != 1
                or sources[0]["id"] != admitted[0]["source_id"]
                or sources[0]["sha256"] != admitted[0]["sha256"]):
            raise ValueError("Native tail extension is bound to the single admitted development source")
        bound = condition["full_pipeline_integration"]["constructor"]
        expected_wire = {"model": bound["requested_model"],
                         "max_completion_tokens": bound["output_token_cap_including_reasoning"],
                         "reasoning_effort": bound["reasoning_effort"], "stream": False, "n": 1}
        if (canonical(policy.wire_parameters) != canonical(expected_wire)
                or policy.timeout_seconds != bound["timeout_seconds_per_request"]):
            raise ValueError("Native tail extension requires the exact admitted wire condition")
    output = Path(output).absolute()
    if output.exists() and any(output.iterdir()):
        raise ValueError("Fresh empty output directory required; no resumed prefix")
    if output.is_symlink() or any(p.is_symlink() for p in output.parents):
        raise ValueError("Unlinked private output required")
    output.mkdir(parents=True, exist_ok=True)
    bindings = [{"id": s["id"], "text_sha256": s["sha256"],
                 "utf8_bytes": len(s["text"].encode("utf-8"))} for s in sources]
    protocol = Path(__file__).with_name("protocol_v1.json")
    manifest = {"protocol": PROTOCOL, "stage": "prepared", "source_bindings": bindings,
                "policy": asdict(policy), "policy_sha256": digest(asdict(policy)),
                "code_sha256": _code_pins(runtime),
                "joint_protocol_sha256": sha256_file(protocol),
                "stages_requested": list(STAGES), "stages": [],
                "provider_revision": "unavailable_unless_runtime_reports_it",
                "context_admission": "Configured engineering limit, not verified provider context; None means unknown",
                "retry_policy": "native validation retries only; unknown execution halts all sends",
                "sampling_equivalence_to_original_transformers": False}
    manifest["complete_native_tail_requested"] = complete_native_tail
    if native is None:
        from Experiments.strict_autoschemakg.contract import verify_source
        manifest["original_source_verification"] = verify_source(source)
    if tail_scope is not None:
        manifest["native_tail_extension"] = {"path": str(Path(native_tail_scope).absolute()),
                                             "sha256": sha256_file(Path(native_tail_scope)),
                                             "scope": tail_scope}
    write_json_atomic(output / "jobmanifest.json", manifest)
    observed = _ObservedRuntime(runtime, output, policy, manifest)
    input_dir = output / "source_input"
    input_dir.mkdir()
    input_file = input_dir / "source.jsonl"
    input_file.write_bytes(b"".join(canonical({"id": s["id"], "text": s["text"],
        "metadata": s.get("metadata", {"lang": "en"})}) + b"\n" for s in sources))
    write_json_atomic(output / "sources.json", sources)
    holder = {}
    context = construction.verified_source_imports(source) if native is None else nullcontext()
    try:
        with context:
            sdk = construction._load_native(source) if native is None else native
            if native is None:
                from atlas_rag.kg_construction.triple_extraction import DatasetProcessor, CustomDataLoader
            else:
                DatasetProcessor, CustomDataLoader = sdk.DatasetProcessor, sdk.CustomDataLoader
            from Tools.experiments.autoschema_ladder_oct14_v1.runner import pipeline_client
            client = pipeline_client(observed)
            client.local_runtime = observed

            def config_factory(**kwargs):
                kwargs.update(batch_size_triple=policy.batch_size, max_workers=1,
                              max_new_tokens=policy.native_output_limit,
                              remove_doc_spaces=policy.remove_doc_spaces,
                              chunk_size=policy.chunk_size, chunk_overlap=policy.chunk_overlap,
                              debug_mode=False, benchmark=False, resume_from=0,
                              deduplicate_text=False, total_shards_triple=1, current_shard_triple=0,
                              total_shards_concept=1, current_shard_concept=0)
                return sdk.ProcessingConfig(**kwargs)

            def extractor_factory(*, model, config):
                extractor = sdk.KnowledgeGraphExtractor(model=model, config=config)
                dataset = extractor.load_dataset()
                processor = DatasetProcessor(config, extractor.prompt_instructions, extractor.result_schema)
                loader = CustomDataLoader(dataset["train"], processor,
                                          extractor.prompt_instructions, extractor.result_schema)
                chunks = deepcopy(loader.processed_data)
                expected = [(x["id"], x["text"], x["metadata"]) for x in chunks]
                if not chunks or set(x[0] for x in expected) != set(s["id"] for s in sources):
                    raise ValueError("Native loader does not cover every requested source")
                holder["chunks"] = chunks
                for chunk in chunks:
                    for key, batch_messages in loader.create_batch_instructions([chunk]).items():
                        for messages in batch_messages:
                            observed.expected_prompts.setdefault(digest(messages), []).append({
                                "source_id": chunk["id"], "chunk_id": chunk["chunk_id"],
                                "category": key, "text_sha256": sha256_text(chunk["text"])})
                manifest.update(native_source_chunks=chunks,
                                extraction_prompt_sha256=deepcopy(observed.expected_prompts),
                                processing_config=asdict(config),
                                native_prompt_template_sha256=digest(extractor.prompt_instructions),
                                native_schema_sha256=digest(extractor.result_schema))
                write_json_atomic(output / "jobmanifest.json", manifest)
                # Reuse the exact already inspected native load; no first-batch projection.
                extractor.load_dataset = lambda: dataset
                holder["extractor"] = extractor
                for stage in STAGES:
                    method = getattr(extractor, stage)

                    def run_stage(*args, _method=method, _stage=stage, **kwargs):
                        observed.phase = _stage
                        entry = {"stage": _stage, "status": "started"}
                        manifest["stages"].append(entry)
                        write_json_atomic(output / "jobmanifest.json", manifest)
                        if _stage == "generate_concept_csv_temp":
                            missing = output / "triples_csv/missing_concepts_source_from_json.csv"
                            with missing.open(encoding="utf-8") as handle:
                                roster = [row for row in list(csv.reader(handle))[1:]
                                          if len(row) > 1 and row[1].lower() in {"entity", "event", "relation"}]
                            concept_count = len(roster)
                            manifest["concept_requests_required_before_dispatch"] = concept_count
                            manifest["native_concept_roster"] = {
                                "source_bindings": bindings, "input_csv_sha256": sha256_file(missing),
                                "items": [{"ordinal": i, "item": row, "sha256": digest(row)}
                                          for i, row in enumerate(roster)]}
                            if tail_scope is not None or complete_native_tail:
                                # Original generate_response has max_retries=3 (four attempts).
                                manifest["native_validation_attempt_limit"] = 4
                                total = (3 * len(chunks) + concept_count) * 4
                                observed.call_limit = total
                                if hasattr(runtime, "max_calls"):
                                    runtime.max_calls = total
                                manifest["derived_complete_native_physical_call_limit"] = total
                            write_json_atomic(output / "jobmanifest.json", manifest)
                            if concept_count > observed.call_limit - len(observed.receipts):
                                entry.update(status="blocked_call_ceiling", required_calls=concept_count,
                                             remaining_calls=observed.call_limit - len(observed.receipts))
                                raise BaselineAbort("Complete native concept tail exceeds bound call ceiling")
                        result = _method(*args, **kwargs)
                        if observed.abort_required or getattr(runtime, "abort_required", False):
                            raise BaselineAbort("Native stage returned after a failed transport")
                        if _stage == "run_extraction":
                            files = sorted((output / "kg_extraction").glob("*.json*"))
                            rows = [json.loads(line) for path in files for line in path.read_text(encoding="utf-8").splitlines() if line]
                            actual = [(x.get("id"), x.get("original_text"), x.get("metadata")) for x in rows]
                            if actual != expected or any(not all(k in x for k in FIELDS) for x in rows):
                                raise BaselineAbort("Native output does not cover all ordered batches/chunks")
                            holder["rows"] = rows
                            write_json_atomic(output / "native_rows.json", rows)
                            write_json_atomic(output / "source_chunks.json", chunks)
                        entry["status"] = "completed"
                        write_json_atomic(output / "jobmanifest.json", manifest)
                        return result

                    setattr(extractor, stage, run_stage)
                return extractor

            injected = SimpleNamespace(**{**vars(sdk), "pipeline": lambda *a, **kw: client,
                "ProcessingConfig": config_factory, "KnowledgeGraphExtractor": extractor_factory})
            native_result = construction.readme_sequence(injected, input_dir, "source", policy.model, output)
            graph_path = Path(native_result["graphml"])
            if not graph_path.is_file():
                raise BaselineAbort("Original graph endpoint missing")
            import networkx as nx
            if native is None:
                from atlas_rag.kg_construction.utils.csv_processing.csv_to_graphml import sanitize_xml_string
            else:
                sanitize_xml_string = getattr(sdk, "sanitize_xml_string", str)
            graph_object = nx.read_graphml(graph_path)
            text_csv = output / "triples_csv/text_nodes_source_from_json.csv"
            # Match original open('r') universal-newline handling exactly.
            with text_csv.open(encoding="utf-8") as handle:
                text_rows = list(csv.DictReader(handle))
            # Match the original export's first occurrence of each passage ID.
            expected_passages = {}
            for row in text_rows:
                key = sanitize_xml_string(str(row["text_id:ID"]))
                expected_passages.setdefault(key, sanitize_xml_string(str(row["original_text"])))
            actual_passages = {str(n): data for n, data in graph_object.nodes(data=True)
                               if data.get("type") == "passage"}
            if (set(actual_passages) != set(expected_passages)
                    or any(actual_passages[k].get("id") != text
                           or actual_passages[k].get("file_id") != k
                           for k, text in expected_passages.items())):
                raise BaselineAbort("Graph passage identities/text differ from the complete native CSV")
            graph_readback = {"GraphML_parsed": True, "nodes": graph_object.number_of_nodes(),
                              "edges": graph_object.number_of_edges(),
                              "passages_match_native_CSV": True,
                              "native_rows": len(holder["rows"]), "native_text_CSV_rows": len(text_rows),
                              "chunk_text_multiset_equals_CSV_text": Counter(x["text"] for x in holder["chunks"])
                                  == Counter(x["original_text"] for x in text_rows),
                              "graph_passages": len(actual_passages),
                              "passages": [{"graph_node_id": k, "id": v["id"], "file_id": v["file_id"]}
                                           for k, v in actual_passages.items()],
                              "native_export_losses_are_not_repaired": True}
            write_json_atomic(output / "graph_readback.json", graph_readback)
        graph = Path(native_result["graphml"])
        if not graph.is_file() or any(s["status"] != "completed" for s in manifest["stages"]):
            raise BaselineAbort("Complete original graph endpoint required")
        result = {"protocol": PROTOCOL, "complete": True, "rows": holder["rows"],
                  "source_chunks": holder["chunks"], "source_bindings": bindings,
                  "graphml": str(graph), "graphml_sha256": sha256_file(graph),
                  "graph_readback": graph_readback,
                  "stages": manifest["stages"], "calls": observed.receipts,
                  "policy_sha256": manifest["policy_sha256"],
                  "scientific_scope": "Technical endpoint, not evidence of semantic quality"}
        manifest["stage"] = "complete"
        write_json_atomic(output / "jobmanifest.json", manifest)
        write_json_atomic(output / "observed_call_index.json", observed.receipts)
        # Publish the success endpoint last, after every mandatory archive.
        write_json_atomic(output / "result.json", result)
        return result
    except BaseException as error:
        manifest.update(stage="incomplete", error_class=type(error).__name__,
                        native_prefix_available="rows" in holder)
        raise
    finally:
        if manifest["stage"] != "complete":
            write_json_atomic(output / "jobmanifest.json", manifest)
            write_json_atomic(output / "observed_call_index.json", observed.receipts)


def materialize(rows, sources, runtime, output, *, policy, source=DEFAULT_SOURCE,
                producer_files=()):
    """Materialize already complete native rows with the existing four-stage tail.

    No extraction occurs. This is a new, explicitly bound suffix condition, not
    recovery or replay of an unknown old concept call. The caller must supply
    complete unique source units and retain their producer/code bindings.
    """
    sources = _sources(sources)
    if (not isinstance(policy, ExecutionPolicy) or type(rows) is not list
            or len(rows) != len(sources) or not callable(getattr(runtime, "generate", None))):
        raise ValueError("Complete source-bound rows and explicit runtime policy required")
    output = Path(output).absolute()
    if output.exists():
        raise ValueError("A new suffix directory is required, never an interrupted prefix")
    for row, src in zip(rows, sources, strict=True):
        if (type(row) is not dict or row.get("id") != src["id"]
                or row.get("original_text") != src["text"]
                or not all(k in row for k in FIELDS)):
            raise ValueError("Whole original SDK rows must match exact ordered source units")
    from Experiments.strict_autoschemakg.contract import verify_source
    tail_module = ROOT / "Tools/abschluss/hipporag2_graph_tail_v1.py"
    code = _code_pins(runtime, (tail_module,))
    parents = {str(Path(p).absolute()): sha256_file(Path(p)) for p in producer_files}
    manifest = {"protocol": PROTOCOL + ":native-suffix", "stage": "prepared",
                "policy": asdict(policy), "policy_sha256": digest(asdict(policy)),
                "code_sha256": code, "producer_file_sha256": parents,
                "source_bindings": [{"id": s["id"], "text_sha256": s["sha256"],
                                     "utf8_bytes": len(s["text"].encode("utf-8"))} for s in sources],
                "native_rows_sha256": digest(rows), "original_source_verification": verify_source(source),
                "joint_protocol_sha256": sha256_file(Path(__file__).with_name("protocol_v1.json")),
                "extraction_invoked": False, "unknown_calls_replayed": False}
    prepared = output.with_name(output.name + ".prepared.json")
    if prepared.exists():
        raise ValueError("Existing suffix claim must not be resumed")
    write_json_atomic(prepared, manifest)
    observed = _ObservedRuntime(runtime, output, policy, manifest)

    def seal_roster():
        path = output / "triples_csv/missing_concepts_source_from_json.csv"
        with path.open(encoding="utf-8") as handle:
            roster = [r for r in list(csv.reader(handle))[1:]
                      if len(r) > 1 and r[1].lower() in {"entity", "event", "relation"}]
        observed.call_limit = max(1, len(roster) * 4)
        if hasattr(runtime, "max_calls"):
            runtime.max_calls = observed.call_limit
        manifest.update(stage="concept_induction", native_concept_roster={
            "source_bindings": manifest["source_bindings"], "input_csv_sha256": sha256_file(path),
            "items": [{"ordinal": i, "item": r, "sha256": digest(r)} for i, r in enumerate(roster)]},
            concept_requests_required_before_dispatch=len(roster), native_validation_attempt_limit=4,
            derived_complete_native_physical_call_limit=observed.call_limit)
        write_json_atomic(output / "jobmanifest.json", manifest)

    observed.before_generate = seal_roster
    try:
        with construction.verified_source_imports(source):
            sdk = construction._load_native(source)
            from Tools.experiments.autoschema_ladder_oct14_v1.runner import pipeline_client
            from Tools.abschluss.hipporag2_graph_tail_v1 import run_graph_tail
            client = pipeline_client(observed)
            generator = sdk.LLMGenerator(client, model_name=policy.model)
            config = sdk.ProcessingConfig(model_path=policy.model, data_directory=str(output.parent),
                filename_pattern="source", output_directory=str(output), max_workers=1,
                batch_size_concept=64, include_concept=True, remove_doc_spaces=policy.remove_doc_spaces)
            extractor = sdk.KnowledgeGraphExtractor(model=generator, config=config)
            manifest["native_prompt_template_sha256"] = digest(extractor.prompt_instructions)
            # The existing tail creates the new directory after validating all inputs.
            tail = run_graph_tail(deepcopy(rows),
                [{"id": s["id"], "text": s["text"], "sha256": s["sha256"]} for s in sources],
                extractor=extractor, runtime=observed)
            if observed.before_generate is not None:
                observed.before_generate = None
                seal_roster()  # Empty native inventory: no inference was necessary.
        if observed.abort_required or getattr(runtime, "abort_required", False):
            raise BaselineAbort("Incomplete suffix must not be published")
        result = {"protocol": PROTOCOL + ":native-suffix", "complete": True, "rows": deepcopy(rows),
                  "source_bindings": manifest["source_bindings"], "graphml": tail["graph"]["path"],
                  "graphml_sha256": tail["graph"]["sha256"], "calls": observed.receipts,
                  "native_tail": tail, "extraction_invoked": False,
                  "scientific_scope": "Technical native materialization, not semantic quality"}
        manifest["stage"] = "complete"
        write_json_atomic(output / "jobmanifest.json", manifest)
        write_json_atomic(output / "observed_call_index.json", observed.receipts)
        write_json_atomic(output / "native_rows.json", rows)
        write_json_atomic(output / "sources.json", sources)
        write_json_atomic(output / "result.json", result)
        return result
    except BaseException as error:
        manifest.update(stage="incomplete", error_class=type(error).__name__)
        write_json_atomic(prepared, manifest)
        if output.is_dir():
            write_json_atomic(output / "jobmanifest.json", manifest)
            write_json_atomic(output / "observed_call_index.json", observed.receipts)
        raise
