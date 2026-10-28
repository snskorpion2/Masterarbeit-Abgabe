"""Opt-in atomic immutable publication. No replacement and no shared lock deletion.

A complete, fsynced same-directory temporary inode is published using an
exclusive hard link (supported on Windows NTFS and POSIX). Unsupported file
systems fail closed rather than falling back to a partial target write.
"""
from contextlib import contextmanager
from contextvars import ContextVar
import json
import os
from pathlib import Path
import tempfile

from .contract import parse_json

PROTOCOL = "same_directory_fsync_exclusive_hardlink_v1"
_enabled = ContextVar("atomic_immutable_publication", default=False)


def enabled():
    return _enabled.get()


def loads(raw):
    """Use the strict parser only inside the opt-in publication scope."""
    if not enabled():
        return json.loads(raw)
    value = parse_json(raw)
    def finite(node):
        if type(node) is float:
            import math
            if not math.isfinite(node):
                raise ValueError("Nonfinite saved JSON number")
        elif isinstance(node, list):
            for child in node:
                finite(child)
        elif isinstance(node, dict):
            for child in node.values():
                finite(child)
    finite(value)
    return value


def read_json(path):
    return loads(Path(path).read_text(encoding="utf-8"))


def equal_json(left, right):
    if not enabled():
        return left == right
    if type(left) is not type(right):
        return False
    if isinstance(left, dict):
        return left.keys() == right.keys() and all(equal_json(left[key], right[key]) for key in left)
    if isinstance(left, list):
        return len(left) == len(right) and all(equal_json(a, b) for a, b in zip(left, right))
    return left == right


@contextmanager
def publication_scope(active=True):
    token = _enabled.set(active)
    try:
        yield
    finally:
        _enabled.reset(token)


def publish_bytes(path, content, *, same=None):
    path = Path(path)
    same = same or (lambda target: target.read_bytes() == content)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if not same(path):
            raise ValueError(f"Immutable artifact changed: {path.name}")
        return
    descriptor, temp = tempfile.mkstemp(prefix="." + path.name + ".", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        try:
            os.link(temp, path)
        except FileExistsError:
            if not same(path):
                raise ValueError(f"Immutable artifact changed: {path.name}")
    finally:
        Path(temp).unlink(missing_ok=True)


def publish_json(path, value):
    # Serialization must finish before either temporary or target creation.
    content = json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False).encode("utf-8")
    publish_bytes(path, content, same=lambda target: equal_json(read_json(target), value))
