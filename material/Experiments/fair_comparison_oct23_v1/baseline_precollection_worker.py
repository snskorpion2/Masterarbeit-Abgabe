"""Fresh OS-process worker for the separately approved blind AS precollection.

No import/preflight dispatches or loads credentials. Native AS prompts, loader,
generator and parser stay original. The one technical change is fail-stop on a
genuine native validation error, before any regeneration or empty fallback.
Progress exposes only transport/status/timing/usage and pins, never values or
object counts. Outcome sealing is a procedure, not a filesystem access claim.
"""
from __future__ import annotations

import argparse
from contextlib import redirect_stderr, redirect_stdout
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
import sys
import time

from Experiments.fair_comparison_oct23_v1 import baseline
from Experiments.fair_comparison_oct23_v1 import baseline_precollection as preparation
from Tools.experiments.fair_tail_oct23_v1 import runtime as existing


PROTOCOL = "blind-original-AS-extraction-worker:oct23-v1"


class WorkerHalt(BaseException):
    """Cannot be swallowed by native Exception-to-empty/retry handlers."""


def require(condition, message):
    if not condition:
        raise WorkerHalt(message)


def load_plan(path, approved_sha256):
    evidence = preparation.pin(path, approved_sha256)
    plan = baseline.construction.json.loads(Path(evidence["path"]).read_bytes())
    require(plan.get("protocol") == preparation.PROTOCOL and plan.get("plan_sha256") == baseline.digest(
        {key:value for key,value in plan.items() if key != "plan_sha256"}), "Frozen source-only plan differs")
    require(plan.get("dispatch_allowed") is False and plan.get("new_model_calls") == 0,
        "Only the untouched prepared plan may receive separate root approval")
    for pin in [*plan["source_pins"], *plan["code_pins"], plan["original_confirmation_gate"]]:
        require(preparation.pin(pin["path"]) == pin, "Bound source/code/protocol changed")
    old = json.loads(Path(plan["original_confirmation_gate"]["path"]).read_bytes())
    require(old["confirmation"]["dispatch_allowed"] is False, "Historical confirmation gate must remain closed")
    require(plan["policy"]["wire_parameters"] == existing.PARAMETERS
        and plan["policy"]["timeout_seconds"] == existing.TIMEOUT,
        "Prospectively fixed DeepSeek wire condition differs")
    flattened = [call for job in plan["jobs"] for call in job["calls"]]
    require(len(flattened) == plan["planned_physical_extraction_POSTs"]
        and len({call["physical_call_id"] for call in flattened}) == len(flattened), "Physical call roster differs")
    for index,call in enumerate(flattened):
        require(call["global_index"] == index and call["payload"] == {
            **existing.PARAMETERS,"messages":call["messages"]}
            and baseline.digest(call["payload"]) == call["payload_sha256"]
            and call["HTTP_timeout_seconds"] == 300 and call["maximum_physical_POSTs"] == 1
            and call["transport_retries"] == call["native_validation_regenerations"] == 0,
            "Original call/parameter/order binding differs")
    require(plan["physical_order"] == [{"physical_call_id":call["physical_call_id"],
        "payload_sha256":call["payload_sha256"]} for call in flattened], "Physical order differs")
    return plan, evidence


class Guard:
    """Compare actual native callbacks and final SDK wire before any POST."""
    def __init__(self, job, transport, output, progress, *, before_first=None, clock=time.monotonic, cpu=time.process_time):
        self.job,self.transport,self.output,self.progress = job,transport,output,progress
        self.clock,self.cpu = clock,cpu
        self.index,self.active_schema,self.expected_native_parameters = 0,None,None
        self.abort_required,self.receipts,self.current = False,[],None
        self.http_timing = {}
        self.pre_wire_rejections = set()
        self.before_first = before_first
        self.metadata = {"backend":"blind-original-AS-precollection","wire_parameters":deepcopy(existing.PARAMETERS)}
        self.tokenizer = None

    def wire_factory(self, reader):
        def factory(old, rows, folder):
            original = existing.one_wire(reader,old,rows,folder)
            guard = self
            class TimedOriginalWire:
                @property
                def attempts(self):
                    return original.attempts
                def __call__(self, config, payload, *, timeout):
                    if not (guard.current is not None and timeout == 300
                        and baseline.canonical(payload) == baseline.canonical(guard.current["payload"])):
                        if guard.current is not None:
                            guard.pre_wire_rejections.add(guard.current["physical_call_id"])
                        raise WorkerHalt("Actual serialized SDK wire differs before HTTP")
                    start,cpu_start = guard.clock(),guard.cpu()
                    try:
                        return original(config,payload,timeout=timeout)
                    finally:
                        guard.http_timing[guard.current["physical_call_id"]] = {
                            "HTTP_wire_wall_seconds":max(0,guard.clock()-start),
                            "local_CPU_seconds_during_HTTP_wire":max(0,guard.cpu()-cpu_start)}
            return TimedOriginalWire()
        return factory

    def generate(self, messages, parameters):
        require(not self.abort_required and self.index < len(self.job["calls"]), "No retry, cache reuse or further dispatch")
        expected = self.job["calls"][self.index]
        require(baseline.canonical(messages) == baseline.canonical(expected["messages"])
            and baseline.canonical(self.active_schema) == baseline.canonical(expected["schema"])
            and baseline.canonical(parameters) == baseline.canonical(self.expected_native_parameters)
            and {**existing.PARAMETERS,"messages":messages} == expected["payload"],
            "Actual native messages/schema/parameters differ before dispatch")
        if self.before_first is not None:
            self.before_first()
        self.current = expected
        folder = self.output / f"call_{self.index:04d}"
        existing.save(folder/"intent.json", {"physical_call_id":expected["physical_call_id"],
            "payload_sha256":expected["payload_sha256"],"unsettled_intent_means_unknown":True})
        row = {"physical_call_id":expected["physical_call_id"],"payload_sha256":expected["payload_sha256"],
            "status":"unknown_execution","POST_attempts":None,"unknown_execution":True,
            "provider_usage":None,"HTTP_wire_wall_seconds":None,"local_CPU_seconds_during_HTTP_wire":None}
        self.receipts.append(row)
        self.index += 1
        start,cpu_start = self.clock(),self.cpu()
        try:
            text = self.transport.generate(deepcopy(messages),deepcopy(parameters))
            receipt = self.transport.receipts[-1]
            require(receipt.get("POST_attempts") == 1 and receipt.get("unknown_execution") is False
                and receipt.get("status") == "completed" and type(text) is str,
                "One confirmed stopped native text completion required")
            for name in ("request","actual_request"):
                require(baseline.canonical(json.loads(Path(receipt[name]["path"]).read_bytes()))
                    == baseline.canonical(expected["payload"]), "Archived actual request differs")
            row.update(status="transport_completed",POST_attempts=1,unknown_execution=False,
                provider_usage=deepcopy(receipt.get("provider_usage")),
                actual_request=deepcopy(receipt["actual_request"]))
            native=receipt.get("native_receipt") or {}
            row.update(http_status=native.get("http_status"),HTTP_body_complete=native.get("HTTP_body_complete"),
                finish_reason=native.get("finish_reason"))
            return text
        except BaseException:
            self.abort_required = True
            if getattr(self.transport,"receipts",None):
                receipt = self.transport.receipts[-1]
                row.update(POST_attempts=receipt.get("POST_attempts"),
                    unknown_execution=receipt.get("unknown_execution",True),
                    provider_usage=deepcopy(receipt.get("provider_usage")))
            if expected["physical_call_id"] in self.pre_wire_rejections:
                # The reused SDK marks its callback entry as a POST attempt.
                # Our final equality guard can prove the underlying HTTP wire
                # was never entered. Preserve the SDK counter, do not count a
                # proven local rejection as a physical model invocation.
                row.update(native_receipt_reported_POST_attempts=row["POST_attempts"],
                    POST_attempts=0,unknown_execution=False,status="local_rejection_before_actual_HTTP_wire")
            else:
                row["status"] = "unknown_execution" if row["unknown_execution"] else "transport_failed"
            raise WorkerHalt("Physical call stopped; no further dispatch or replay") from None
        finally:
            row.update(self.http_timing.get(expected["physical_call_id"],{}))
            row["transport_callback_wall_seconds_including_archival"] = max(0,self.clock()-start)
            row["transport_callback_local_CPU_seconds"] = max(0,self.cpu()-cpu_start)
            existing.save(folder/"transport_status.json",row)
            self.progress(row)


def run_job(job, sdk, output, transport_factory, progress, *, before_first=None):
    from Tools.experiments.autoschema_ladder_oct14_v1.runner import pipeline_client
    from atlas_rag.kg_construction.triple_extraction import DatasetProcessor, CustomDataLoader
    from atlas_rag.llm_generator.format.validate_json_output import validate_output,fix_triple_extraction_response
    output.mkdir(parents=True,exist_ok=False)
    guard = Guard(job,None,output/"guard",progress,before_first=before_first)
    guard.transport = transport_factory(output/"transport",len(job["calls"]),guard)
    guard.transport.phase = "run_extraction"
    generator = sdk.LLMGenerator(pipeline_client(guard),model_name=existing.MODEL,max_workers=1)
    config = sdk.ProcessingConfig(**{**job["processing_config"],
        "data_directory":str(output/"source_input"),"output_directory":str(output)})
    source = job["source_only_input"]
    existing.save(output/"source_input/source.jsonl",baseline.canonical({"id":source["id"],"text":source["text"],
        "metadata":source.get("metadata",{"lang":"en"})})+b"\n")
    extractor = sdk.KnowledgeGraphExtractor(model=generator,config=config)
    dataset = extractor.load_dataset()
    processor = DatasetProcessor(config,extractor.prompt_instructions,extractor.result_schema)
    loader = CustomDataLoader(dataset["train"],processor,extractor.prompt_instructions,extractor.result_schema)
    require(baseline.canonical(loader.processed_data) == baseline.canonical(job["original_chunks"]),
        "Actual original loader chunks differ from the frozen plan")
    actual_calls = []
    for messages,_,_,_ in loader:
        for category,items in messages.items():
            actual_calls.extend({"messages":item,"schema":extractor.result_schema[category]} for item in items)
    require(len(actual_calls)==len(job["calls"]) and all(
        baseline.canonical(actual)==baseline.canonical({"messages":expected["messages"],"schema":expected["schema"]})
        for actual,expected in zip(actual_calls,job["calls"],strict=True)), "Whole native call roster differs")
    # Bind actual HF callback kwargs from the unchanged original generation config.
    native_config = deepcopy(generator.config)
    native_config.max_tokens = config.max_new_tokens
    guard.expected_native_parameters = native_config.to_huggingface_params()
    require(guard.expected_native_parameters.get("max_new_tokens")==8192
        and guard.expected_native_parameters.get("temperature")==0.7,
        "Original generator parameters differ from the primary wire condition")
    original_generate = generator.generate_response
    parser_cpu, parser_failed = [], [False]
    def failstop_generate(*args,**kwargs):
        require(kwargs.get("validate_function") is validate_output
            and kwargs.get("fix_function") is fix_triple_extraction_response
            and baseline.canonical(kwargs.get("schema"))==baseline.canonical(guard.active_schema),
            "Unchanged native validation chain required")
        def original_validation(text,**options):
            start=time.process_time()
            try:
                return validate_output(text,**options)
            except Exception:
                parser_failed[0] = True
                guard.abort_required = True
                raise WorkerHalt("Genuine native validation failure; no regeneration or empty fallback") from None
            finally:
                parser_cpu.append(max(0,time.process_time()-start))
        return original_generate(*args,**{**kwargs,"max_retries":0,"validate_function":original_validation})
    generator.generate_response = failstop_generate
    original_stage = extractor.process_stage
    def bound_stage(instructions,result_schema):
        guard.active_schema = deepcopy(result_schema)
        return original_stage(instructions,result_schema)
    extractor.process_stage = bound_stage
    extractor.load_dataset = lambda:dataset
    try:
        extractor.run_extraction()
        require(not guard.abort_required and guard.index==len(job["calls"]), "Complete native extraction required")
        files=list((output/"kg_extraction").glob("*.json*"))
        require(len(files)==1,"One complete original source output required")
        # Mechanical carrier validation only. No outcome values or object counts
        # enter progress, stdout, the return value or the worker status.
        rows=[json.loads(line) for line in files[0].read_bytes().splitlines()]
        require(len(rows)==len(loader.processed_data) and all(row.get("id")==chunk["id"]
            and row.get("original_text")==chunk["text"] and all(type(row.get(field)) is list for field in baseline.FIELDS)
            for row,chunk in zip(rows,loader.processed_data,strict=True)),"Native carrier/source binding differs")
        row_pin=existing.save(output/"native_rows.private.json",rows)
        return {"status":"completed","native_carrier":row_pin,
            "native_parser_local_CPU_seconds":sum(parser_cpu),"physical_calls_completed":guard.index}
    finally:
        existing.save(output/"native_parser_CPU_status.json",{"native_parser_local_CPU_seconds":sum(parser_cpu),
            "genuine_validation_failure":parser_failed[0]})


def run(plan_path, output, *, approved_plan_file_sha256, approved_worker_sha256,
        transport_factory=None):
    require(sha256(Path(__file__).read_bytes()).hexdigest()==approved_worker_sha256,"Exact externally reviewed worker code required")
    require(sys.flags.utf8_mode,"Use a fresh Python -X utf8 OS process")
    plan,plan_pin = load_plan(plan_path,approved_plan_file_sha256)
    claim_path=Path(plan_pin["path"]).with_name("execution-claim-"+approved_plan_file_sha256+".json")
    require(not claim_path.exists(),"Existing plan execution claim blocks every replay, including another output path")
    output=Path(output).resolve()
    require(not output.exists() and not output.is_relative_to(baseline.ROOT.resolve())
        and not output.is_relative_to(Path(plan_pin["path"]).parent),"Fresh separate private output required; never resume")
    output.mkdir(parents=True,exist_ok=False)
    # Snapshot code before constructing any provider/client or POST. The plan
    # itself stays at its original path; no second mutable plan copy is made.
    code=[preparation.pin(__file__),*plan["code_pins"]]
    for relative,meta in plan["original_sdk_verification"]["files"].items():
        code.append(preparation.pin(Path(plan["original_sdk_verification"]["directory"])/relative,meta["sha256"]))
    snapshots=[]
    for index,pin in enumerate(code):
        saved=existing.save(output/"code-snapshots"/(str(index).zfill(4)+"-"+Path(pin["path"]).name),Path(pin["path"]).read_bytes())
        require(saved["sha256"]==pin["sha256"],"Code snapshot drift")
        snapshots.append({"original":pin,"snapshot":saved})
    existing.save(output/"worker-condition.json",{"protocol":PROTOCOL,"original_prepared_plan":plan_pin,
        "root_approval_of_plan_file_sha256":approved_plan_file_sha256,
        "root_approval_of_worker_sha256":approved_worker_sha256,"code_snapshots":snapshots,
        "blinding_rule":plan["blinding"],"outcome_sealing_is_procedure_not_filesystem_security":True,
        "schema_graph_or_evaluation_started":False,"separate_OS_process_utf8":True})
    technical=[]
    claimed=[False]
    def claim_execution():
        if not claimed[0]:
            existing.save(claim_path,{"protocol":PROTOCOL,"plan":plan_pin,"worker_sha256":approved_worker_sha256,
                "execution_output":str(output),"unsettled_claim_blocks_replay":True,
                "automatic_recovery_or_resume_allowed":False})
            claimed[0]=True
    def progress(row):
        technical.append(deepcopy(row))
        existing.save(output/"progress"/(str(len(technical)).zfill(4)+".json"),row)
    status={"protocol":PROTOCOL,"status":"started","source_draw_jobs_completed":0,
        "physical_callbacks_observed":0,"known_POST_attempts":0,"unknown_execution":False,"provider_usage":None}
    started,cpu_started=time.monotonic(),time.process_time()
    try:
        with (output/"native_console.private.log").open("x",encoding="utf8") as console:
            with redirect_stdout(console),redirect_stderr(console):
                with baseline.construction.verified_source_imports(baseline.DEFAULT_SOURCE):
                    sdk=baseline.construction._load_native(baseline.DEFAULT_SOURCE)
                    if transport_factory is None:
                        # Reuse the existing native DS wire, not a reviewer engine.
                        reader,_,_=existing.definitions(existing.READER)
                        def transport_factory(path,max_calls,guard):
                            return existing.MantleTailRuntime(path,max_calls=max_calls,
                                wire_factory=guard.wire_factory(reader))
                    for index,job in enumerate(plan["jobs"]):
                        load_plan(plan_path,approved_plan_file_sha256)
                        result=run_job(job,sdk,output/"jobs"/str(index).zfill(3),transport_factory,progress,
                            before_first=claim_execution)
                        existing.save(output/"jobs"/str(index).zfill(3)/"carrier_status.json",result)
                        status["source_draw_jobs_completed"]+=1
        require(len(technical)==plan["planned_physical_extraction_POSTs"],"Full physical roster required")
        status["status"]="completed"
    except BaseException as error:
        status.update(status="stopped_no_replay",error_class=type(error).__name__)
        if isinstance(error,WorkerHalt):
            status["technical_stop_reason"]=str(error)
    finally:
        http=[row["HTTP_wire_wall_seconds"] for row in technical
            if type(row.get("HTTP_wire_wall_seconds")) in (int,float)]
        status.update(physical_callbacks_observed=len(technical),
            known_POST_attempts=sum(row["POST_attempts"] for row in technical if type(row.get("POST_attempts")) is int),
            unknown_execution=any(row.get("unknown_execution") is not False for row in technical),
            known_HTTP_wire_wall_seconds=sum(http),
            HTTP_wire_wall_seconds=sum(http) if len(http)==len(technical) else None,
            HTTP_wire_timing_observations=len(http),
            worker_total_wall_seconds=max(0,time.monotonic()-started),
            worker_local_CPU_seconds=max(0,time.process_time()-cpu_started),
            actual_outcome_values_reported=False,actual_object_counts_reported=False)
        usages=[row.get("provider_usage") for row in technical]
        fields=("prompt_tokens","completion_tokens","total_tokens")
        status["known_provider_tokens"]={key:sum(usage[key] for usage in usages
            if type(usage) is dict and type(usage.get(key)) is int) for key in fields}
        status["provider_usage"]=status["known_provider_tokens"] if usages and all(type(usage) is dict
            and all(type(usage.get(key)) is int for key in fields) for usage in usages) else None
        existing.save(output/"final_status.json",status)
    return status


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan",type=Path,required=True)
    parser.add_argument("--output",type=Path,required=True)
    parser.add_argument("--approved-plan-file-sha256",required=True)
    parser.add_argument("--approved-worker-sha256",required=True)
    args=parser.parse_args()
    status=run(args.plan,args.output,approved_plan_file_sha256=args.approved_plan_file_sha256,
        approved_worker_sha256=args.approved_worker_sha256)
    print(baseline.canonical(status).decode())
    return 0 if status["status"]=="completed" else 2


if __name__=="__main__":
    raise SystemExit(main())
