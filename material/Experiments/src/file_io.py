"""Small UTF-8/hash primitives with explicit existing output profiles.

No canonicalization, JSON repair or stricter semantic admission is performed.
Text writers retain platform newline translation. Atomic checkpoints retain
their binary UTF-8 profile without a trailing newline.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import tempfile
from threading import Lock

_atomic_replace_lock = Lock()


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload, *, trailing_newline: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(payload, ensure_ascii=False, indent=2)
    path.write_text(text + ("\n" if trailing_newline else ""), encoding="utf-8")


def write_json_atomic(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb", dir=path.parent, prefix=f".{path.name}.", suffix=".tmp", delete=False,
        ) as handle:
            tmp_path = Path(handle.name)
            handle.write(json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8"))
        with _atomic_replace_lock:
            tmp_path.replace(path)
    finally:
        if tmp_path is not None:
            tmp_path.unlink(missing_ok=True)
