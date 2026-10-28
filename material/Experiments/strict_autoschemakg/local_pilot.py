"""Prepare one unchanged article or check the two explicitly selected models."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time

from .contract import new_output, write_json
from .local_runtime import LocalOllama, PROFILES, request_json
from .pilot_sampling import positive_integer, validate_repetitions

ARTICLE = Path(__file__).resolve().parents[1] / "data/corpus/Leslie Lamport.txt"
REPOSITORY = Path(__file__).resolve().parents[2]


def run_pilot(output, judge_repetitions=3):
    """Retain a failed checkpoint for process and post-stage failures alike."""
    try:
        validate_repetitions(judge_repetitions)
        return _run_pilot(output, judge_repetitions)
    except BaseException as exc:
        checkpoint = Path(output) / "pilot_summary.json"
        summary = json.loads(checkpoint.read_text(encoding="utf-8")) if checkpoint.exists() else {"stages": []}
        summary.update(status="failed", error_type=type(exc).__name__, scientific_claim=False)
        write_json(checkpoint, summary)
        raise


def _run_pilot(output, judge_repetitions):
    """One article, five native construction steps and original evaluators."""
    output = output.resolve()
    summary = {"status": "running", "article": "Leslie Lamport", "scientific_claim": False,
               "evaluation_protocol": "pilot_balanced_repetitions",
               "judge_repetitions_per_passage": judge_repetitions,
               "schema_quality": "not scored, pending validated evaluation", "stages": []}

    def stage(name, module, arguments):
        started = time.perf_counter()
        command = [sys.executable, "-X", "utf8", "-B", "-m", module, *map(str, arguments)]
        result = subprocess.run(command, cwd=REPOSITORY, check=False)
        summary["stages"].append({"name": name, "command": command,
                                  "returncode": result.returncode,
                                  "elapsed_seconds": time.perf_counter() - started})
        if result.returncode:
            summary["status"] = "failed"
        write_json(output / "pilot_summary.json", summary)
        if result.returncode:
            raise RuntimeError(f"Pilot stage {name} failed. See its manifest and native log.")

    stage("input", "Experiments.strict_autoschemakg.local_pilot",
          ["prepare", "--output", output / "input"])
    runner = "Experiments.strict_autoschemakg.run"
    stage("construct", runner, ["construct", "--data-directory", output / "input",
          "--filename-prefix", "lamport", "--model", next(iter(PROFILES)),
          "--local-models", "--output", output / "construct", "--execute"])
    extraction = list((output / "construct" / "kg_extraction").glob("*.json"))
    if len(extraction) != 1:
        raise RuntimeError("Expected exactly one native extraction file")
    judge = ["--model", "Qwen/Qwen3.5-4B", "--local-models", "--execute"]
    stage("info-questions", runner, ["info-questions", "--input", extraction[0],
          "--output", output / "questions", "--mcq-json-fence-bridge", *judge])
    questions = output / "questions" / "native" / "mcq.jsonl"
    for context in ("empty", "passage", "entity", "event_only", "event"):
        stage("info-answers-" + context, runner,
              ["info-answers", "--input", questions, "--context-type", context,
               "--output", output / ("answers_" + context), *judge])
    stage("triple-accuracy", runner, ["triple-accuracy", "--input", extraction[0],
          "--output", output / "triple_accuracy", "--pilot-judge-repetitions", judge_repetitions, *judge])
    summary["status"] = "pilot_stages_returned_review_outputs"
    write_json(output / "pilot_summary.json", summary)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("prepare", "smoke", "run"))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--judge-repetitions", type=positive_integer, default=3)
    args = parser.parse_args()
    if args.action in {"run", "smoke"} and request_json("/api/ps").get("models"):
        raise RuntimeError("Ollama still has a loaded model. Unload it before the sequential local pilot.")
    output = new_output(args.output)
    if args.action == "run":
        try:
            run_pilot(output, judge_repetitions=args.judge_repetitions)
        finally:
            request_json("/api/generate", {"model": PROFILES["Qwen/Qwen3.5-4B"]["ollama_model"],
                                          "keep_alive": 0})
        return
    if args.action == "prepare":
        raw = ARTICLE.read_bytes()
        text = raw.decode("utf-8-sig")
        record = {"id": "Leslie Lamport", "text": text,
                  "metadata": {"title": "Leslie Lamport", "source": "local Wikipedia corpus"}}
        (output / "lamport.jsonl").write_text(json.dumps(record, ensure_ascii=False) + "\n", encoding="utf-8")
        write_json(output / "input_manifest.json", {
            "source": str(ARTICLE), "source_sha256": hashlib.sha256(raw).hexdigest(),
            "article_count": 1, "text_characters": len(text), "text_words": len(text.split()),
            "methodological_preprocessing": "none, UTF-8 decode and native JSONL packaging only",
        })
        print(f"Prepared one unchanged article: {output / 'lamport.jsonl'}")
        return
    reports = []
    for index, model in enumerate(PROFILES):
        folder = output / str(index)
        folder.mkdir()
        runtime = LocalOllama(model, folder)
        try:
            answer = runtime.generate([
                {"role": "user", "content": 'Reply with exactly this JSON object and nothing else: {"ready":true}'},
            ], {"max_new_tokens": 64, "temperature": 0.7, "do_sample": True,
                "return_full_text": False, "truncation": True, "padding": False})
            if json.loads(answer) != {"ready": True}:
                raise RuntimeError("Local smoke response failed the JSON contract")
            report = {"model": model, "status": "json_smoke_passed", "quality_validated": False}
            reports.append(report)
            print(json.dumps(report), flush=True)
        finally:
            runtime.close()
            request_json("/api/generate", {"model": runtime.name, "keep_alive": 0})
    write_json(output / "report.json", {"models": reports, "scientific_claim": False})


if __name__ == "__main__":
    main()
