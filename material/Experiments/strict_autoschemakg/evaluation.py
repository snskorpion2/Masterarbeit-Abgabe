"""Technical bindings around the pinned, unchanged AutoSchemaKG evaluators.

The caller verifies the pinned checkout before calling ``evaluate``. This module
does not port prompts, parsers, sampling, or metric implementations. Each run
executes those implementations from that checkout. No model imports happen at
module import time. The command-line entry point owns execution approval and
stdout capture. This module is not safe for concurrent calls in one process
because the original scripts use process-wide argv, random and logging state.
"""
from __future__ import annotations

import asyncio
from contextlib import contextmanager
import csv
import hashlib
import importlib.util
import json
import logging
import os
from pathlib import Path
import re
import runpy
import shutil
import sys
from types import SimpleNamespace
from typing import Callable


SCHEMA_PROFILES = frozenset({"YAGO43kET", "FB15kET", "FB15kRT", "wikihow"})
CONTEXT_TYPES = frozenset({"empty", "passage", "entity", "event_only", "event"})
STAGES = frozenset({"triple-accuracy", "info-questions", "info-answers", "schema-concepts", "schema-score"})


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON object key in evaluator input")
        result[key] = value
    return result


def _non_finite(_):
    raise ValueError("Non-finite JSON number")


def _jsonl(path: Path) -> list[dict]:
    """Fail before a run instead of silently changing the evaluated population."""
    rows = []
    with path.open(encoding="utf-8") as stream:
        for number, line in enumerate(stream, 1):
            try:
                value = json.loads(line, object_pairs_hook=_unique_object,
                                   parse_constant=_non_finite)
            except (json.JSONDecodeError, ValueError) as exc:
                raise ValueError(f"Invalid JSONL record at line {number}") from exc
            if not isinstance(value, dict):
                raise ValueError(f"Expected JSON object at line {number}")
            rows.append(value)
    if not rows:
        raise ValueError("Evaluator input must contain at least one record")
    return rows


def _input_file(path: Path | None, name: str) -> Path:
    if path is None or not Path(path).is_file():
        raise ValueError(f"{name} must be an existing file")
    return Path(path).resolve()


def _extraction_rows(input_path: Path):
    rows = _jsonl(_input_file(input_path, "input_path"))
    staged = []
    renamed = 0
    for row in rows:
        if "event_entity_dict" in row and "event_entity_relation_dict" in row:
            raise ValueError("Ambiguous EV fields: both original and evaluator names exist")
        if "event_entity_dict" in row:
            renamed += 1
            row = {("event_entity_relation_dict" if key == "event_entity_dict" else key): value
                   for key, value in row.items()}
        if not isinstance(row.get("original_text"), str):
            raise ValueError("Evaluator input requires original_text as a string")
        for key in ("entity_relation_dict", "event_entity_relation_dict", "event_relation_dict"):
            if not isinstance(row.get(key), list):
                raise ValueError(f"Evaluator input requires a list in {key}")
        staged.append(row)
    return staged, renamed


def stage_extraction_input(input_path: Path, destination: Path) -> dict:
    """Rename only the top-level EV key in a separate, exclusively created file.

    JSON serialization may differ, but all decoded values, list/record order
    and object-key positions remain identical. ASCII escapes also preserve
    Unicode through the original triple evaluator's platform-default reader.
    """
    staged, renamed = _extraction_rows(input_path)
    with destination.open("x", encoding="utf-8", newline="\n") as stream:
        for row in staged:
            stream.write(json.dumps(row, ensure_ascii=True, allow_nan=False) + "\n")
    return {"records": len(staged), "renamed_records": renamed,
            "source_sha256": hashlib.sha256(Path(input_path).read_bytes()).hexdigest(),
            "staged_sha256": hashlib.sha256(destination.read_bytes()).hexdigest(),
            "staged_file": str(destination)}


def load_native(source: Path, relative: str):
    """Load one verified-checkout script without its __main__ block."""
    root = (Path(source).resolve() / "EvaluateKGC").resolve()
    path = (root / relative).resolve()
    if not path.is_relative_to(root) or not path.is_file():
        raise ValueError("Original evaluator path escapes the verified checkout or is missing")
    name = "_strict_autoschemakg_" + hashlib.sha256(str(path).encode()).hexdigest()
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load original evaluator {relative}")
    module = importlib.util.module_from_spec(spec)
    # Compile the exact verified source bytes, never a possibly stale .pyc.
    exec(compile(path.read_bytes(), str(path), "exec"), module.__dict__)
    if Path(module.__file__).resolve() != path:
        raise ImportError("Original evaluator import provenance mismatch")
    return module


def bind_model_factory(factory: Callable, model: str) -> Callable:
    """Bind only the model field that triple_acc.py hardcodes in its SDK call."""
    def bound_factory(*args, **kwargs):
        client = factory(*args, **kwargs)
        native_create = client.chat.completions.create

        def create(*request_args, **request_kwargs):
            return native_create(*request_args, **dict(request_kwargs, model=model))

        return SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
    return bound_factory


def bind_metric_device(score: Callable, device: str) -> Callable:
    """Change CUDA placement only, not the metric model or its parameters."""
    def bound_score(*args, **kwargs):
        return score(*args, **dict(kwargs, device=device))
    return bound_score


@contextmanager
def _native_process(argv: list[str]):
    previous_argv = sys.argv
    logger = logging.getLogger()
    previous_handlers = list(logger.handlers)
    previous_level = logger.level
    sys.argv = argv
    try:
        yield
    finally:
        sys.argv = previous_argv
        for handler in list(logger.handlers):
            if handler not in previous_handlers:
                logger.removeHandler(handler)
                handler.close()
        logger.setLevel(previous_level)


def _credentials() -> tuple[str, str]:
    key = os.environ.get("AUTOSCHEMAKG_API_KEY")
    url = os.environ.get("AUTOSCHEMAKG_BASE_URL")
    if not key or not url:
        raise ValueError("Set AUTOSCHEMAKG_API_KEY and AUTOSCHEMAKG_BASE_URL before API evaluation")
    return key, url


def _schema_paths(dataset, triple_file, type_file):
    dataset = dataset or "YAGO43kET"
    if dataset not in SCHEMA_PROFILES:
        raise ValueError("Unknown native schema profile. Use YAGO43kET, FB15kET, FB15kRT or wikihow")
    paths = {}
    if dataset != "wikihow":
        paths["triple_file"] = _input_file(triple_file, "triple_file")
    if dataset != "FB15kRT":
        paths["type_file"] = _input_file(type_file, "type_file")
    return dataset, paths


def _validate_tsv(path: Path, width: int):
    count = 0
    with path.open(encoding="utf-8") as stream:
        for count, line in enumerate(stream, 1):
            if len(line.strip().split("\t")) != width:
                raise ValueError(f"Native schema input requires {width} TSV columns at line {count}")
    if not count:
        raise ValueError("Schema input must not be empty")


def validate_evaluation_inputs(stage: str, *, input_path: Path | None = None,
                               model: str | None = None, dataset: str | None = None,
                               triple_file: Path | None = None, type_file: Path | None = None,
                               context_type: str = "event",
                               metric_device: str | None = None) -> list[Path]:
    """Offline, read-only input contract. Does not import any model dependency."""
    if stage not in STAGES:
        raise ValueError(f"Unknown original evaluation stage: {stage}")
    if model is not None and not model.strip():
        raise ValueError("Model must not be empty")
    if context_type not in CONTEXT_TYPES or (stage != "info-answers" and context_type != "event"):
        raise ValueError("Context selection is only valid for info-answers")
    if stage == "schema-score" and model is not None:
        raise ValueError("schema-score fixes the original metric model roberta-large")
    if metric_device is not None and (stage != "schema-score" or re.fullmatch(r"cuda:(0|[1-9][0-9]*)", metric_device) is None):
        raise ValueError("metric_device is a CUDA placement cuda:N for schema-score only")
    if not stage.startswith("schema-") and (triple_file is not None or type_file is not None):
        raise ValueError("Schema source files are only valid for schema stages")
    if stage == "triple-accuracy" and dataset is not None:
        raise ValueError("triple-accuracy has no dataset profile parameter")
    if stage == "schema-concepts" and input_path is not None:
        raise ValueError("schema-concepts uses triple_file/type_file, not input_path")
    paths = []
    if stage.startswith("schema-"):
        dataset, schema_paths = _schema_paths(dataset, triple_file, type_file)
        if dataset == "wikihow" and triple_file is not None:
            raise ValueError("Native wikihow schema profile does not use triple_file")
        if dataset == "FB15kRT" and type_file is not None:
            raise ValueError("Native FB15kRT schema profile does not use type_file")
        for name, path in schema_paths.items():
            _validate_tsv(path, 3 if name == "triple_file" else 2)
            paths.append(path)
    if stage in {"triple-accuracy", "info-questions", "info-answers", "schema-score"}:
        path = _input_file(input_path, "input_path")
        paths.insert(0, path)
        if stage in {"triple-accuracy", "info-questions"}:
            _extraction_rows(path)
        elif stage == "info-answers":
            for row in _jsonl(path):
                if not isinstance(row.get("passage"), str):
                    raise ValueError("MCQ input requires passage")
                for key in ("entity_relation_list", "event_entity_list", "event_relation_list"):
                    if not isinstance(row.get(key), list) or not all(isinstance(item, str) for item in row[key]):
                        raise ValueError(f"MCQ input requires string list {key}")
                if not isinstance(row.get("mcq_list"), list):
                    raise ValueError("MCQ input requires mcq_list")
                for question in row["mcq_list"]:
                    if (not isinstance(question, dict)
                            or not isinstance(question.get("question"), str)
                            or not isinstance(question.get("answer"), str)
                            or not isinstance(question.get("options"), list)
                            or len(question["options"]) != 4
                            or not all(isinstance(option, str) for option in question["options"])):
                        raise ValueError("MCQ input requires question, answer and four string options")
        else:
            # Original schema prediction writer/reader use locale defaults.
            with path.open(newline="") as stream:
                rows = list(csv.reader(stream))
            if len(rows) < 2:
                raise ValueError("Schema prediction CSV requires a header and data rows")
    return paths


def _schema_score(source: Path, argv: list[str], metric_device: str | None = None) -> dict:
    # Optional explicit hardware placement leaves embeddings, precision,
    # matching and denominator semantics untouched. Default remains native.
    import torch
    device = metric_device or "cuda:4"
    index = int(device.split(":")[1])
    if not torch.cuda.is_available() or torch.cuda.device_count() <= index:
        raise RuntimeError(f"schema-score requires available device {device}")
    native_utils = load_native(source, "SchemaQuality/utils.py")
    if metric_device is not None:
        native_utils.score_bert = bind_metric_device(native_utils.score_bert, device)
    previous_utils = sys.modules.get("utils")
    sys.modules["utils"] = native_utils
    try:
        with _native_process(argv):
            runpy.run_path(str(Path(source).resolve() / "EvaluateKGC/SchemaQuality/eval.py"), run_name="__main__")
    finally:
        if previous_utils is None:
            sys.modules.pop("utils", None)
        else:
            sys.modules["utils"] = previous_utils
    return {"native_metrics": "stdout", "metric_model": "roberta-large", "metric_device": device,
            "metric_device_binding": metric_device is not None}


def evaluate(source: Path, stage: str, *, input_path: Path | None = None,
             model: str | None = None, dataset: str | None = None,
             triple_file: Path | None = None, type_file: Path | None = None,
             context_type: str = "event", metric_device: str | None = None,
             output: Path, local_ollama: bool = False, mcq_json_fence_bridge: bool = False,
             pilot_judge_repetitions: int | None = None, repair_technical_retries: bool = False) -> dict:
    """Native evaluation, with an optional explicitly non-original pilot schedule."""
    if pilot_judge_repetitions is not None:
        from .pilot_sampling import validate_repetitions
        validate_repetitions(pilot_judge_repetitions)
        if stage != "triple-accuracy":
            raise ValueError("Pilot repetitions apply only to triple-accuracy")
    validate_evaluation_inputs(stage, input_path=input_path, model=model, dataset=dataset,
                               triple_file=triple_file, type_file=type_file,
                               context_type=context_type, metric_device=metric_device)
    if not Path(output).is_dir():
        raise ValueError("output must be a fresh run directory created by the caller")
    if mcq_json_fence_bridge and (stage != "info-questions" or not local_ollama):
        raise ValueError("MCQ format bridge is only valid for local info-questions")
    local_runtime = None
    if local_ollama:
        if stage == "schema-score":
            raise ValueError("Local generative binding is not a schema metric replacement")
        from .local_runtime import LocalOllama
        local_runtime = LocalOllama(model, output)
    credentials = (("local-unused", "http://127.0.0.1:11434") if local_ollama else
                   None if stage == "schema-score" else _credentials())
    schema_paths = {}
    if stage.startswith("schema-"):
        dataset, schema_paths = _schema_paths(dataset, triple_file, type_file)
    if stage in {"triple-accuracy", "info-questions", "info-answers", "schema-score"}:
        input_path = _input_file(input_path, "input_path")
    work = Path(output).resolve() / "native"
    work.mkdir(exist_ok=False)
    argv = [stage]
    result = {"stage": stage, "native_metrics": "stdout"}
    if mcq_json_fence_bridge:
        result["mcq_format_bridge"] = "remove_valid_json_fence_label_only"

    if stage in {"triple-accuracy", "info-questions"}:
        inputs = work / "input"
        inputs.mkdir()
        staged = inputs / "extraction.jsonl"
        result["format_bridge"] = stage_extraction_input(input_path, staged)
    elif stage == "info-answers":
        _jsonl(input_path)
        staged = work / "questions.jsonl"
        shutil.copyfile(input_path, staged)
    if stage.startswith("schema-"):
        argv += ["--dataset", dataset]
        for name, path in schema_paths.items():
            staged_path = work / (name + ".txt")
            shutil.copyfile(path, staged_path)
            argv += ["--" + name, str(staged_path)]
        if stage == "schema-score":
            prediction = work / "prediction.csv"
            shutil.copyfile(input_path, prediction)
            argv += ["--pred_file", str(prediction)]
            return dict(result, **_schema_score(source, argv, metric_device))

    if stage == "triple-accuracy":
        native = load_native(source, "TripleAccuracy/triple_acc.py")
        native.API_KEY, native.BASE_URL = credentials
        if local_runtime:
            native.OpenAI = local_runtime.sdk_factory(bind_model=True)
            if repair_technical_retries:
                from tenacity import retry_if_exception
                from .retry_policy import transient_transport
                native.response = native.response.retry_with(
                    retry=retry_if_exception(transient_transport))
                result["technical_retry_policy"] = "native ceiling unchanged, transient transport only"
        elif repair_technical_retries:
            raise ValueError("Repair retry policy requires explicit local models")
        elif model:
            native.OpenAI = bind_model_factory(native.OpenAI, model)
        sampling = {"mode": "original_random_with_replacement", "requested_draws": 100}
        attempted = 100
        if pilot_judge_repetitions is None:
            native.main_for_one_file(str(staged))
        else:
            from .pilot_sampling import sampling_scope
            with sampling_scope(native, result["format_bridge"]["records"], pilot_judge_repetitions) as sampling:
                native.main_for_one_file(str(staged))
            attempted = len(sampling["passage_indices"])
        csv_file = staged.with_name(staged.stem + "_cleaned.csv")
        # This is the exact aggregation expression in the original __main__.
        df = native.pd.read_csv(csv_file)
        print(df.iloc[:, 1:].mean())
        with csv_file.open(encoding="utf-8", newline="") as stream:
            completed = max(sum(1 for _ in csv.reader(stream)) - 1, 0)
        from .pilot_sampling import summarize_csv
        from .contract import write_json
        write_json(Path(output) / "metric_summary.json", summarize_csv(csv_file))
        return dict(result, output_file=str(csv_file), attempted_draws=attempted,
                    sampling=sampling, completed_draws=completed,
                    native_cost_is_character_estimate=True)

    scripts = {"info-questions": "InfoPreservation/question_generation.py",
               "info-answers": "InfoPreservation/answer_generation.py",
               "schema-concepts": "SchemaQuality/conceptualization_contextulized_api.py"}
    native = load_native(source, scripts[stage])
    native.API_KEY, native.BASE_URL = credentials
    if local_runtime:
        native.AsyncOpenAI = local_runtime.sdk_factory(
            asynchronous=True, mcq_json_fence_bridge=mcq_json_fence_bridge,
        )
    output_file = work / ("concepts.csv" if stage == "schema-concepts" else "mcq.jsonl" if stage == "info-questions" else "answers.jsonl")
    argv += ["--output_file", str(output_file), "--logging_file", str(work / "native.log")]
    if model:
        argv += ["--model", model]
    if not stage.startswith("schema-"):
        argv += ["--kg_file", str(staged.parent if stage == "info-questions" else staged)]
        if dataset:
            argv += ["--dataset", dataset]
    if stage == "info-answers":
        argv += ["--context_type", context_type]
    with _native_process(argv):
        asyncio.run(native.main())
    if stage == "info-answers":
        return dict(result, context_type=context_type, native_writes_answer_file=False)
    result["output_file"] = str(output_file)
    if stage == "info-questions":
        with output_file.open(encoding="utf-8") as stream:
            result["output_records"] = sum(1 for _ in stream)
    return result
