"""One source/draw native schema tail over a separately confirmed SDK carrier.

Preparation reads only explicitly bound inputs. Execution requires separate Main
admission and injected, reviewed runtime/technical validation helpers. No schema,
prompt, extractor, exporter or model loader is reimplemented here.
"""
from copy import deepcopy
from dataclasses import asdict
from hashlib import sha256
from io import BytesIO
from pathlib import Path
import sys
import time

from Experiments.fair_comparison_oct23_v1 import baseline


PROTOCOL = "source-draw-confirmed-carrier-native-tail-worker:oct23-v1"
CANDIDATE = "AS_SCOPE_JOINT_ROW_V1"
WIRE = {"model": "deepseek.v3.2", "temperature": 0.7, "max_tokens": 8192, "stream": False}


class WorkerHalt(BaseException):
    """Terminal worker failure; native Exception handlers cannot replay it."""


def require(ok, message):
    if not ok:
        raise WorkerHalt(message)


def pin(path):
    path = Path(path).absolute()
    require(path.is_file() and not any(p.is_symlink() or getattr(p, "is_junction", lambda: False)()
            for p in (path, *path.parents)), "Regular unlinked bound file required")
    raw = path.read_bytes()
    return {"path": str(path), "bytes": len(raw), "sha256": sha256(raw).hexdigest()}


def checked(item, *, parse=False):
    path = Path(item["path"]).absolute()
    require(path.is_file() and not any(p.is_symlink() or getattr(p, "is_junction", lambda: False)()
            for p in (path, *path.parents)), "Regular unlinked bound file required")
    raw = path.read_bytes()
    require(str(path) == item["path"] and len(raw) == item["bytes"]
            and sha256(raw).hexdigest() == item["sha256"], "Consumed input binding differs")
    if not parse:
        return raw
    from Experiments.strict_autoschemakg.contract import parse_json
    return parse_json(raw)


def _fresh(output):
    output = Path(output).absolute()
    require(output.parent.is_dir() and not output.exists(), "Fresh private cell output required")
    require(not output.resolve().is_relative_to(baseline.ROOT.resolve()), "Private output outside repository required")
    require(not any(p.is_symlink() or getattr(p, "is_junction", lambda: False)()
            for p in (output, *output.parents)), "Unlinked output required")
    for suffix in (".prepared.json", ".cell-claim.json", ".worker-result.json"):
        require(not output.with_name(output.name + suffix).exists(), "Existing cell cannot be resumed or replayed")
    return output


def prepare_cell(*, baseline_plan_binding, job_id, source_manifest_binding, case_id, document_id,
                 system, draw_id, rows_binding, producer_receipts, producer_complete,
                 output_root, runtime_binding, code_bindings):
    """Prepare exactly one prebound original chunk; no .env, runtime or model."""
    require(system in ("AS", CANDIDATE) and type(draw_id) is int and draw_id in (1, 2, 3),
            "Explicit system and integer draw1..3 required")
    require(type(producer_receipts) is list and producer_receipts and producer_complete is True,
            "Actual producer bindings and external completeness attestation required")
    require(type(code_bindings) is list and code_bindings, "Main's explicit reviewed code bindings required")
    for item in [baseline_plan_binding, source_manifest_binding, rows_binding, runtime_binding,
                 *producer_receipts, *code_bindings]:
        checked(item)
    bound = checked(baseline_plan_binding, parse=True)
    jobs = [job for job in bound["jobs"] if job.get("job_id") == job_id]
    require(len(jobs) == 1, "One original source-only baseline job required")
    job = jobs[0]
    require(job["draw_id"] == ("draw_1", "draw_2", "draw_3")[draw_id - 1]
            and job["source_id"] == case_id, "Baseline case/draw binding differs")
    manifest = checked(source_manifest_binding, parse=True)
    cases = [case for case in manifest["cases"] if case.get("id") == case_id]
    require(len(cases) == 1 and len(cases[0]["documents"]) == 1, "One original manifest case/document required")
    document = cases[0]["documents"][0]
    require(document["id"] == document_id, "Explicit QA document ID differs from original manifest")
    source = baseline._sources([job["source_only_input"]])[0]
    require(source["id"] == case_id and source["sha256"] == job["source_sha256"] == document["sha256"],
            "Full raw source identity/hash differs from manifest")
    chunks = job["original_chunks"]
    require(type(chunks) is list and len(chunks) == 1 and chunks[0]["id"] == source["id"]
            and type(chunks[0]["text"]) is str and bool(chunks[0]["text"]),
            "Exactly one prebound original SDK chunk required")
    rows = checked(rows_binding, parse=True)
    require(type(rows) is list and len(rows) == 1 and type(rows[0]) is dict
            and rows[0].get("id") == chunks[0]["id"] and rows[0].get("original_text") == chunks[0]["text"]
            and all(type(rows[0].get(key)) is list for key in baseline.FIELDS)
            and "event_entity_relation_dict" not in rows[0], "Whole native carrier differs from prebound original chunk")
    policy = baseline.ExecutionPolicy(**deepcopy(job["execution_policy"]))
    require(baseline.canonical(policy.wire_parameters) == baseline.canonical(WIRE)
            and policy.model == WIRE["model"] and policy.timeout_seconds == 300
            and policy.native_output_limit == 8192, "Fixed DS3.2 sampling/context-output condition differs")
    config = job["processing_config"]
    require(all(config.get(key) == getattr(policy, key) for key in
                ("chunk_size", "chunk_overlap", "remove_doc_spaces")), "Original source processing policy differs")
    chunk = {"id": chunks[0]["id"], "text": chunks[0]["text"],
             "sha256": sha256(chunks[0]["text"].encode("utf-8")).hexdigest()}
    output = _fresh(output_root)
    value = {"protocol": PROTOCOL, "system": system, "draw_id": draw_id, "case_id": case_id,
        "document_id": document_id, "sourceSDK_id": chunk["id"], "job_id": job_id,
        "baseline_plan_binding": deepcopy(baseline_plan_binding), "source_manifest_binding": deepcopy(source_manifest_binding),
        "rows_binding": deepcopy(rows_binding), "producer_receipts": deepcopy(producer_receipts),
        "producer_completeness_attested_externally": True, "raw_source_sha256": source["sha256"],
        "source_chunk": chunk, "processing_config": deepcopy(config), "execution_policy": asdict(policy),
        "runtime_binding": deepcopy(runtime_binding), "code_bindings": deepcopy(code_bindings),
        "worker_binding": pin(__file__), "baseline_binding": pin(baseline.__file__),
        "output_root": str(output), "transport_retries": 0, "extraction_invoked": False,
        "dispatch_allowed_by_prepare": False, "new_model_calls": 0,
        "provider_weight_revision": None, "models_attested_by_this_worker": False}
    value["plan_sha256"] = baseline.digest(value)
    return value


def _verify(plan):
    require(plan.get("protocol") == PROTOCOL and plan.get("plan_sha256") == baseline.digest(
        {key: value for key, value in plan.items() if key != "plan_sha256"}), "Prepared cell plan differs")
    for key in ("baseline_plan_binding", "source_manifest_binding", "rows_binding", "runtime_binding",
                "worker_binding", "baseline_binding"):
        checked(plan[key])
    for item in [*plan["producer_receipts"], *plan["code_bindings"]]:
        checked(item)


def _save_new(path, value):
    from Experiments.strict_autoschemakg.immutable_publish import publish_bytes
    publish_bytes(path, baseline.canonical(value), same=lambda _: False)


class _RuntimeGuard:
    def __init__(self, runtime, plan):
        self.runtime, self.plan = runtime, plan
        self.unreceipted_entries = 0

    def __getattr__(self, name):
        return getattr(self.runtime, name)

    @property
    def phase(self):
        return self.runtime.phase

    @phase.setter
    def phase(self, value):
        self.runtime.phase = value

    @property
    def max_calls(self):
        return self.runtime.max_calls

    @max_calls.setter
    def max_calls(self, value):
        self.runtime.max_calls = value

    def generate(self, messages, parameters):
        _verify(self.plan)
        require(self.phase == "concept_induction", "Only original concept induction may dispatch")
        before = len(self.runtime.receipts)
        try:
            return self.runtime.generate(messages, parameters)
        finally:
            if len(self.runtime.receipts) == before:
                self.unreceipted_entries += 1


def run_cell(plan, *, runtime_factory, admission, roster_validator, endpoint_resolver=None):
    """Run an admitted, fresh native cell using reviewed injected helpers only.

    roster_validator(result, output) must check the callback count and produced
    concept CSV multiset against the original sealed roster; native shuffle does
    not imply any CSV-to-callback ordinal mapping. endpoint_resolver(output) must
    replay original CSV-order get_node_id bindings and reject aliases. Main pins
    these concrete helper implementations before admitting an actual cell.
    """
    _verify(plan)
    require(type(admission) is dict and admission.get("protocol") == PROTOCOL + ":Main-admission"
            and admission.get("dispatch_allowed") is True and admission.get("admitted_by") == "Main"
            and admission.get("plan_sha256") == plan["plan_sha256"]
            and admission.get("runtime_binding") == plan["runtime_binding"]
            and admission.get("code_bindings") == plan["code_bindings"], "Exact separate Main admission required")
    require(sys.flags.utf8_mode and callable(runtime_factory) and callable(roster_validator),
            "Fresh UTF-8 process and reviewed runtime/roster helpers required")
    require(plan["system"] == "AS" or callable(endpoint_resolver), "Candidate requires reviewed original endpoint replay")
    output = _fresh(plan["output_root"])
    claim = output.with_name(output.name + ".cell-claim.json")
    _save_new(claim, {"protocol": PROTOCOL, "plan_sha256": plan["plan_sha256"], "unsettled_claim_is_not_success": True})
    began = time.monotonic()
    runtime, guard = None, None
    result = {"protocol": PROTOCOL, "plan_sha256": plan["plan_sha256"],
        "complete": False, "failure": None, "system": plan["system"], "draw_id": plan["draw_id"],
        "case_id": plan["case_id"], "document_id": plan["document_id"], "sourceSDK_id": plan["sourceSDK_id"],
        "extraction_invoked": False, "automatic_replay": False, "physical_POSTs": None, "unknown_executions": None}
    try:
        runtime = runtime_factory(output, max_calls=plan["execution_policy"]["max_calls"])
        require(getattr(runtime, "receipts", None) == [] and getattr(runtime, "abort_required", True) is False
                and Path(runtime.output).absolute() == output, "Fresh matching runtime required")
        guard = _RuntimeGuard(runtime, plan)
        rows = checked(plan["rows_binding"], parse=True)
        producer_paths = [item["path"] for item in [plan["baseline_plan_binding"], plan["source_manifest_binding"],
            plan["rows_binding"], *plan["producer_receipts"]]]
        native = baseline.materialize(rows, [deepcopy(plan["source_chunk"])], guard, output,
            policy=baseline.ExecutionPolicy(**plan["execution_policy"]), producer_files=producer_paths)
        _verify(plan)
        require(native.get("complete") is True and native.get("extraction_invoked") is False,
                "Native source cell tail did not complete")
        roster = roster_validator(native, output)
        require(type(roster) is dict and roster.get("complete") is True and roster.get("multiset_equal") is True
                and type(roster.get("expected_calls")) is int and roster["expected_calls"] == len(native["calls"])
                and type(roster.get("actual_calls")) is int and roster["actual_calls"] == roster["expected_calls"],
                "Actual concept callbacks and final CSV multiset must equal complete native roster")
        receipts = runtime.receipts
        require(guard.unreceipted_entries == 0 and len(receipts) == len(native["calls"]) and not runtime.abort_required
                and all(type(row.get("POST_attempts")) is int and row["POST_attempts"] == 1 and row.get("unknown_execution") is False
                        and row.get("status") == "completed" for row in receipts), "Every physical concept call must be confirmed once")
        require(all(call.get("phase") == "concept_induction" and call.get("status") == "completed"
                    and call.get("runtime_receipt") == receipt
                    for call, receipt in zip(native["calls"], receipts, strict=True)),
                "Every native callback must bind its actual physical concept receipt")
        graph = pin(native["graphml"])
        require(graph["sha256"] == native["graphml_sha256"], "Native actual graph changed")
        result.update(native_result=pin(output / "result.json"), native_graph=graph, roster_evidence=roster)
        if plan["system"] != "AS":
            import networkx as nx
            from Tools.experiments.as_parallel_export_oct20_v1.export_control import export_control
            relation_csv, endpoints, evidence = endpoint_resolver(output)
            require(Path(relation_csv).absolute() == output / "concept_csv/triple_edges_source_from_json_with_concept.csv",
                    "Candidate must use actual final concept-bearing Relation CSV")
            exported = export_control(nx.read_graphml(BytesIO(checked(graph))), relation_csv, endpoints,
                                      output / "candidate-row-preserving.graphml")
            checked(graph)
            result.update(endpoint_evidence=evidence, row_export=exported,
                          graph_file=pin(output / "candidate-row-preserving.graphml"))
        else:
            result["graph_file"] = graph
        _verify(plan)
        result["complete"] = True
    except BaseException as error:
        result["failure"] = {"error_class": type(error).__name__, "native_result_alone_is_not_worker_success": True}
    finally:
        if runtime is not None:
            result["physical_call_receipts"] = deepcopy(getattr(runtime, "receipts", []))
            receipts = result["physical_call_receipts"]
            if all(type(row.get("POST_attempts")) is int for row in receipts):
                result["physical_POSTs"] = sum(row["POST_attempts"] for row in receipts)
            if all(type(row.get("unknown_execution")) is bool for row in receipts):
                result["unknown_executions"] = sum(row["unknown_execution"] for row in receipts)
        result["unreceipted_runtime_entries"] = 0 if guard is None else guard.unreceipted_entries
        if result["unreceipted_runtime_entries"]:
            result["receipted_POSTs_only"] = result["physical_POSTs"]
            result["physical_POSTs"] = result["unknown_executions"] = None
        result["wall_seconds"] = time.monotonic() - began
        _save_new(output.with_name(output.name + ".worker-result.json"), result)
    return result
