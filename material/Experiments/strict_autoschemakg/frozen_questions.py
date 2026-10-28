"""Version the approved Q2 wording, never regenerate or overwrite old questions."""
import copy
import hashlib
import json
from pathlib import Path
import re

from . import extended_artifacts as artifacts
from .contract import DEFAULT_SOURCE, sha256
from .evaluation import load_native

VERSION = "lamport_mcq_q2_explicit_first_release_v1"
Q2 = "According to the passage, which version of Lamport’s LaTeX macros was the first whose release date is explicitly stated, and when was it released?"


def prepare(original, article):
    original, article = Path(original), Path(article)
    base = original.parents[2]
    record = json.loads(original.read_text(encoding="utf-8"))
    questions = artifacts.load_questions(original)
    source_manifest_path = base / "input/input_manifest.json"
    source_manifest = json.loads(source_manifest_path.read_text(encoding="utf-8"))
    prepared_path = base / "input/lamport.jsonl"
    prepared = json.loads(prepared_path.read_text(encoding="utf-8"))
    text = article.read_bytes().decode("utf-8-sig")
    if source_manifest["source_sha256"] != sha256(article) or prepared["text"] != text:
        raise ValueError("Frozen questions source provenance changed")
    passage = re.sub(r"\s+", " ", text).strip()
    if record["passage"] != passage:
        raise ValueError("Frozen questions full passage does not match the prepared source")
    native = load_native(DEFAULT_SOURCE, "InfoPreservation/question_generation.py")
    prompt = native.MCQ_PROMPT.replace("{passage}", passage)
    calls_path = base / "questions/calls.jsonl"
    calls = [json.loads(line) for line in calls_path.read_text(encoding="utf-8").splitlines()]
    if len(calls) != 1 or calls[0]["messages"] != [{"role": "user", "content": prompt}]:
        raise ValueError("Original question generation prompt provenance changed")
    if questions[1]["answer"] != "B":
        raise ValueError("Frozen original Q2 key changed")
    revised = copy.deepcopy(record)
    revised["mcq_list"][1]["question"] = Q2
    provenance = {"version": VERSION, "source_original_sha256": sha256(article),
                  "source_manifest_sha256": sha256(source_manifest_path),
                  "prepared_source_sha256": sha256(prepared_path), "prepared_source_id": prepared["id"],
                  "full_passage_sha256": hashlib.sha256(passage.encode()).hexdigest(),
                  "original_questions_path": str(original.resolve()), "original_questions_sha256": sha256(original),
                  "generation_calls_sha256": sha256(calls_path),
                  "original_generation_prompt_sha256": hashlib.sha256(prompt.encode()).hexdigest(),
                  "original_question": questions[1]["question"], "changed_question": Q2,
                  "reason": "Specify the first release with an explicitly stated date, not an ambiguous development-chain beginning.",
                  "options_and_key_unchanged": True, "regenerated": False}
    return revised, provenance


def persist(output, record, provenance):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    for name, value in (("mcq.jsonl", record), ("provenance.json", provenance)):
        path = output / name
        if path.exists():
            if json.loads(path.read_text(encoding="utf-8")) != value:
                raise ValueError("Immutable frozen question version changed")
        else:
            with path.open("x", encoding="utf-8") as stream:
                stream.write(json.dumps(value, ensure_ascii=False, allow_nan=False) + "\n")
    return output / "mcq.jsonl"
