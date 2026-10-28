"""Offline integrity checks. This module never imports model libraries."""

import ast
import hashlib
import importlib.metadata
import json
import locale
import os
import platform
import subprocess
import sys
from pathlib import Path

PIN = "d0a1666ae6621806faf814504c73678de4e809f2"
DEFAULT_SOURCE = Path(__file__).resolve().parents[2] / "Tools/ReferenceRepos/benchmark_autoschemakg_original"
SOURCE_AREAS = ("atlas_rag", "EvaluateKGC", "README.md", "pyproject.toml", "LICENSE")


def _git(source, *args):
    result = subprocess.run(
        ["git", "-C", str(source), *args], capture_output=True, check=False,
    )
    if result.returncode:
        raise ValueError("Originalcheckout nicht lesbar: " + result.stderr.decode("utf-8", errors="replace").strip())
    return result.stdout


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def verify_source(source):
    """Compare executable sources to the pinned Git objects, not just git status.

    Explicit byte comparison also catches assume-unchanged/skip-worktree files.
    Only checkout CRLF/LF conversion is tolerated. Dataset bytes are recorded
    separately for the selected run and are not treated as method source.
    """
    source = Path(source).resolve()
    git_root = Path(_git(source, "rev-parse", "--show-toplevel").decode().strip()).resolve()
    if git_root != source:
        raise ValueError("Der Originalcheckout muss eine eigene Git-Wurzel sein.")
    commit = _git(source, "rev-parse", "HEAD").decode().strip()
    if commit != PIN:
        raise ValueError(f"Falscher Original-Commit: {commit}, erwartet {PIN}.")
    tree = _git(source, "ls-tree", "-r", "-z", "HEAD", *SOURCE_AREAS)
    entries = {}
    for entry in tree.split(b"\0"):
        if not entry:
            continue
        meta, name = entry.split(b"\t", 1)
        mode, kind, oid = meta.decode().split()
        relative = name.decode("utf-8")
        if "/data/" in relative and not relative.endswith(".py"):
            continue
        if kind != "blob" or mode not in ("100644", "100755"):
            raise ValueError(f"Unerwarteter Quelltyp: {relative}")
        entries[relative] = oid
    if not entries:
        raise ValueError("Keine Originalquellen gefunden.")
    # One subprocess rather than one per source file.
    batch = subprocess.run(
        ["git", "-C", str(source), "cat-file", "--batch"],
        input=("\n".join(entries.values()) + "\n").encode(),
        capture_output=True, check=True,
    ).stdout
    offset = 0
    files = {}
    for relative, oid in entries.items():
        end = batch.index(b"\n", offset)
        _, kind, size = batch[offset:end].split()
        if kind != b"blob":
            raise ValueError(f"Ungültiges Quellobjekt: {relative}")
        start = end + 1
        expected = batch[start:start + int(size)]
        offset = start + int(size) + 1
        path = source / relative
        if not path.is_file() or path.is_symlink():
            raise ValueError(f"Fehlende oder verlinkte Quelle: {relative}")
        actual = path.read_bytes()
        if actual.replace(b"\r\n", b"\n") != expected.replace(b"\r\n", b"\n"):
            raise ValueError(f"Geänderte Originalquelle: {relative}")
        files[relative] = {"git_blob": oid, "sha256": hashlib.sha256(actual).hexdigest()}
    # Reject untracked/ignored source overlays, including import shadowing.
    for area in ("atlas_rag", "EvaluateKGC"):
        for path in (source / area).rglob("*"):
            if path.is_file() and path.suffix in (".py", ".so", ".pyd"):
                if path.relative_to(source).as_posix() not in entries:
                    raise ValueError(f"Zusätzliche ausführbare Quelle: {path.relative_to(source)}")
    return {"commit": commit, "directory": str(source), "files": files}


def verify_imports(source):
    package = Path(source).resolve() / "atlas_rag"
    for name, module in tuple(sys.modules.items()):
        if name == "atlas_rag" or name.startswith("atlas_rag."):
            origin = getattr(module, "__file__", None)
            if not origin or not Path(origin).resolve().is_relative_to(package):
                raise ValueError(f"Fremder Original-Import: {name}")


def new_output(path):
    path = Path(path).resolve()
    if path.exists():
        raise ValueError(f"Ausgabepfad existiert bereits: {path}")
    path.mkdir(parents=True, exist_ok=False)
    return path


def parse_json(text):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"Doppelter JSON-Schlüssel: {key}")
            result[key] = value
        return result
    def invalid(value):
        raise ValueError(f"Ungültige JSON-Zahl: {value}")
    return json.loads(text, object_pairs_hook=unique, parse_constant=invalid)


def runtime_versions():
    return {
        "python": sys.version,
        "platform": platform.platform(),
        "utf8_mode": sys.flags.utf8_mode,
        "preferred_encoding": locale.getpreferredencoding(False),
        "python_hash_seed": os.environ.get("PYTHONHASHSEED"),
        "cuda_visible_devices": os.environ.get("CUDA_VISIBLE_DEVICES"),
        "packages": dict(sorted(
            (dist.metadata["Name"], dist.version)
            for dist in importlib.metadata.distributions() if dist.metadata["Name"]
        )),
    }


def original_defaults(source, stage):
    """Observe native literals without importing or overriding their execution."""
    if stage == "construct":
        observed = {}
        for relative, class_name in (
            ("atlas_rag/kg_construction/triple_config.py", "ProcessingConfig"),
            ("atlas_rag/llm_generator/generation_config.py", "GenerationConfig"),
        ):
            tree = ast.parse((Path(source) / relative).read_text(encoding="utf-8"))
            class_def = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == class_name)
            observed[class_name + "_class_defaults"] = {
                node.target.id: ast.literal_eval(node.value) for node in class_def.body
                if isinstance(node, ast.AnnAssign) and node.value is not None
            }
        observed["README_overrides"] = {
            "batch_size_triple": 3, "batch_size_concept": 16, "max_new_tokens": 2048,
            "max_workers": 3, "remove_doc_spaces": True, "concept_call_batch_size": 64,
        }
        return observed
    relative = {
        "triple-accuracy": "TripleAccuracy/triple_acc.py",
        "info-questions": "InfoPreservation/question_generation.py",
        "info-answers": "InfoPreservation/answer_generation.py",
        "schema-concepts": "SchemaQuality/conceptualization_contextulized_api.py",
        "schema-score": "SchemaQuality/eval.py",
    }[stage]
    tree = ast.parse((Path(source) / "EvaluateKGC" / relative).read_text(encoding="utf-8"))
    defaults = {}
    seeds = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
            continue
        if node.func.attr == "add_argument":
            for keyword in node.keywords:
                if keyword.arg == "default":
                    flags = [ast.literal_eval(arg) for arg in node.args]
                    name = next((flag for flag in flags if flag.startswith("--")), flags[0])
                    defaults[name] = ast.literal_eval(keyword.value)
        if node.func.attr == "seed" and isinstance(node.func.value, ast.Name) and node.func.value.id == "random":
            seeds.append(ast.literal_eval(node.args[0]))
    return {"script": relative, "native_cli_defaults": defaults,
            "native_random_seed_calls": seeds,
            "technical_bindings_listed_separately": True}


def write_json(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
