"""The five README calls, without own extraction or schema logic."""

import dataclasses
import hashlib
import json
import os
import sys
from pathlib import Path
from types import SimpleNamespace

from .contract import verify_imports, write_json
from .source_imports import verified_source_imports

DEFAULT_MODEL = "meta-llama/Llama-3.1-8B-Instruct"


def dataset_files(directory, pattern):
    directory = Path(directory).resolve()
    if not directory.is_dir():
        raise ValueError("Der Datensatzpfad muss ein vorhandenes Verzeichnis sein.")
    if not pattern or any(c in pattern for c in "/\\*?[]") or pattern in (".", ".."):
        raise ValueError("Dateimuster muss ein nichtleerer einfacher Dateipräfix sein.")
    # Deliberately identical to native load_dataset: no sorting or sampling.
    files = [directory / name for name in os.listdir(directory)
             if name.startswith(pattern) and name.endswith((".json.gz", ".json", ".jsonl", ".jsonl.gz"))]
    if not files or any(not path.is_file() for path in files):
        raise ValueError("Keine passenden Datensatzdateien gefunden.")
    return files


def _load_native(source):
    verify_imports(source)
    previous_path = list(sys.path)
    sys.path.insert(0, str(Path(source).resolve()))
    try:
        from atlas_rag.kg_construction.triple_extraction import KnowledgeGraphExtractor
        from atlas_rag.kg_construction.triple_config import ProcessingConfig
        from atlas_rag.llm_generator import LLMGenerator
        from transformers import pipeline
        verify_imports(source)
        return SimpleNamespace(
            KnowledgeGraphExtractor=KnowledgeGraphExtractor, ProcessingConfig=ProcessingConfig,
            LLMGenerator=LLMGenerator, pipeline=pipeline,
        )
    finally:
        sys.path[:] = previous_path


def _settings(client, generator, config):
    local_runtime = vars(client).get("local_runtime")
    model = getattr(client, "model", None)
    tokenizer = getattr(client, "tokenizer", None)
    model_config = getattr(model, "config", None)
    generation = getattr(model, "generation_config", None)
    chat_template = getattr(tokenizer, "chat_template", None)
    tokenizer_kwargs = getattr(tokenizer, "init_kwargs", {})
    return {
        "processing_config": dataclasses.asdict(config) if dataclasses.is_dataclass(config) else None,
        "generation_config": dataclasses.asdict(generator.config) if dataclasses.is_dataclass(generator.config) else None,
        "model_generation_config": generation.to_dict() if generation is not None else None,
        "model_revision": getattr(model_config, "_commit_hash", None),
        "tokenizer_revision": tokenizer_kwargs.get("_commit_hash"),
        "tokenizer_class": type(tokenizer).__name__ if tokenizer is not None else None,
        "chat_template_sha256": hashlib.sha256(json.dumps(chat_template, sort_keys=True).encode()).hexdigest(),
        "concept_call_batch_size": 64,
        "backend": local_runtime.metadata["backend"] if local_runtime is not None else "transformers.pipeline",
    }


def readme_sequence(native, data_directory, filename_pattern, model, output, local_ollama=False, extraction_only=False):
    if local_ollama:
        from .local_runtime import local_pipeline
        client = local_pipeline(model, output)
    else:
        client = native.pipeline("text-generation", model=model, device_map="auto")
    triple_generator = native.LLMGenerator(client, model_name=model)
    config = native.ProcessingConfig(
        model_path=model, data_directory=str(data_directory), filename_pattern=filename_pattern,
        batch_size_triple=3, batch_size_concept=16, output_directory=str(output),
        max_new_tokens=2048, max_workers=3, remove_doc_spaces=True,
    )
    # Sidecar observation only. No native generation/configuration mutation.
    write_json(Path(output) / "native_settings.json", _settings(client, triple_generator, config))
    extractor = native.KnowledgeGraphExtractor(model=triple_generator, config=config)
    extractor.run_extraction()
    if extraction_only:
        return {"construction_mode": "extraction_only", "induction_enabled": False,
                "graph_build_enabled": False}
    extractor.convert_json_to_csv()
    extractor.generate_concept_csv_temp(batch_size=64)
    extractor.create_concept_csv()
    extractor.convert_to_graphml()
    return {"graphml": str(Path(output) / "kg_graphml" / f"{filename_pattern}_graph.graphml")}


def construct(source, *, data_directory, filename_pattern, model, output, local_ollama=False, extraction_only=False):
    with verified_source_imports(source):
        return readme_sequence(_load_native(source), data_directory, filename_pattern, model, output, local_ollama, extraction_only)
