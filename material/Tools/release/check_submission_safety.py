"""CPU-only safety audit of an explicit, hash-bound submission file list.

This checks selected bytes, not Git history, licensing or semantic personal data.
Findings never contain matching snippets or credential values. Exit 0 means the
technical checks passed; exit 2 means at least one check failed.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import sys
import unicodedata

PROTOCOL = "masterarbeit-submission-safety-v1"
DEFAULT_MAX_FILE_BYTES = 25 * 1024 * 1024
BLOCKED_PARTS = {
    ".git", ".env", ".venv", "venv", "node_modules", "__pycache__",
    "private", "private_raw", "private_raw_responses", "private_evidence",
    "masterarbeit-private-evidence", "raw", "raw_responses", "raw_outputs",
    "gold", "gold_sealed", "models", "model", "runtime", "runtimes",
    "hf_home", "pip_cache", "wheels", "appdata", "vladspersonalspace",
}
BLOCKED_NAMES = {"serverzugang.md", "opencode_config.json", "gold_sealed.json", "gold.json"}
BLOCKED_SUFFIXES = {".raw", ".pem", ".key", ".p12", ".pfx", ".safetensors", ".gguf", ".whl"}
DATA_SUFFIXES = {".json", ".jsonl", ".ndjson", ".csv", ".tsv", ".yaml", ".yml", ".xml",
                 ".txt", ".bin", ".parquet", ".db", ".sqlite", ".npy", ".npz", ".pkl", ".pickle"}
WINDOWS_RESERVED = {"con", "prn", "aux", "nul", *[f"{p}{n}" for p in ("com", "lpt") for n in range(1, 10)]}

# Patterns are data, not exemptions: the checker is scanned by the same rules.
CONTENT_RULES = (
    ("private_absolute_windows_path", re.compile(rb"(?i)(?<![a-z0-9])[a-z]:[/\\]+[^\s\"'<>]{1,}")),
    ("private_absolute_unix_path", re.compile(rb"/(?:home|Users|root)/[^\s\"'<>]+")),
    ("private_storage_reference", re.compile(rb"(?i)\b(?:appdata|masterarbeit-private-evidence|private[_-]evidence)[/\\]+")),
    ("private_key_material", re.compile(rb"-----BEGIN (?:[A-Z0-9]+ )?PRIVATE KEY-----")),
    ("aws_access_key", re.compile(rb"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b")),
    ("provider_api_key", re.compile(rb"\bsk-(?:proj-|ant-api\d\d-)?[A-Za-z0-9_-]{25,}\b")),
    ("github_token", re.compile(rb"\b(?:ghp_|github_pat_)[A-Za-z0-9_]{25,}\b")),
    ("huggingface_token", re.compile(rb"\bhf_[A-Za-z0-9]{30,}\b")),
    ("bearer_credential", re.compile(rb"(?i)\bbearer\s+[a-z0-9._~+/-]{20,}={0,2}")),
    ("azure_sas_signature", re.compile(rb"(?i)(?:[?&]|&amp;)sig=[a-z0-9%+/_=-]{20,}")),
    ("literal_secret_assignment", re.compile(
        rb"(?im)(?<![a-z0-9_])[\"']?(?:[a-z0-9_-]+[_-])?"
        rb"(?:api[_-]?key|secret(?:[_-]access[_-]key)?|access[_-]token|auth[_-]token|"
        rb"password|passwd|aws[_-]key|nvidia[_-]nim)[\"']?\s*[:=]\s*"
        rb"[\"'][a-z0-9+/_=.~-]{16,}[\"']")),
    ("unquoted_secret_assignment", re.compile(
        rb"(?im)^[ \t]*(?:export[ \t]+)?[\"']?(?:[a-z0-9_-]+[_-])?"
        rb"(?:api[_-]?key|secret(?:[_-]access[_-]key)?|access[_-]token|auth[_-]token|"
        rb"password|passwd|aws[_-]key|nvidia[_-]nim)[\"']?[ \t]*[:=][ \t]*"
        rb"[a-z0-9+/_=~-]{20,}[ \t]*(?:\#.*)?$")),
)


def strict_json(data: bytes):
    """Reject ambiguous duplicate keys and non-JSON floating point constants."""
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("duplicate JSON key")
            result[key] = value
        return result
    return json.loads(data.decode("utf-8-sig"), object_pairs_hook=unique,
                      parse_constant=lambda _: (_ for _ in ()).throw(ValueError("nonfinite JSON")))


def relative_name(value: object) -> str:
    if (not isinstance(value, str) or not value
            or any(ord(c) < 32 or unicodedata.category(c) in {"Cs", "Cf"} for c in value)):
        raise ValueError("invalid path")
    if any(c in value for c in '\\:*?<>|"\x7f') or value.startswith("/"):
        raise ValueError("nonportable path")
    parts = value.split("/")
    if any(p in ("", ".", "..") or p.endswith((".", " ")) for p in parts):
        raise ValueError("noncanonical path")
    if any(p.split(".")[0].casefold() in WINDOWS_RESERVED for p in parts):
        raise ValueError("reserved path")
    if PurePosixPath(value).as_posix() != value:
        raise ValueError("noncanonical path")
    return value


def blocked_path(name: str) -> bool:
    p = PurePosixPath(name)
    parts = [part.casefold() for part in p.parts]
    return (any(part in BLOCKED_PARTS or part.startswith(".env.") for part in parts)
            or p.name.casefold() in BLOCKED_NAMES
            or (p.suffix.casefold() in DATA_SUFFIXES and p.stem.casefold() in BLOCKED_PARTS)
            or p.suffix.casefold() in BLOCKED_SUFFIXES
            or any(".private." in part or part.endswith(".private") for part in parts))


def _label(value: object, ordinal: int) -> str:
    """Never echo malformed paths, private absolute paths or secret-bearing names."""
    try:
        name = relative_name(value)
    except ValueError:
        return f"<entry:{ordinal}>"
    raw = name.encode("utf-8")
    if len(raw) > 512 or any(pattern.search(raw) for _, pattern in CONTENT_RULES):
        return f"<entry:{ordinal}>"
    return name


def _no_links(path: Path) -> None:
    for item in (path, *path.parents):
        s = item.lstat()
        if stat.S_ISLNK(s.st_mode) or getattr(s, "st_file_attributes", 0) & 0x400:
            raise ValueError("linked path")


def _read_checked(root: Path, name: str, limit: int) -> bytes:
    path = root.joinpath(*PurePosixPath(name).parts)
    _no_links(path)
    if not path.resolve(strict=True).is_relative_to(root):
        raise ValueError("escaped root")
    info = path.stat()
    if not stat.S_ISREG(info.st_mode):
        raise ValueError("not a regular file")
    if info.st_size > limit:
        raise OverflowError("too large")
    flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(path, flags)
    with os.fdopen(fd, "rb") as stream:
        opened = os.fstat(stream.fileno())
        _no_links(path)
        current = path.stat()
        if (opened.st_dev, opened.st_ino, opened.st_size, opened.st_mtime_ns) != (
                current.st_dev, current.st_ino, current.st_size, current.st_mtime_ns):
            raise ValueError("file changed")
        body = stream.read(limit + 1)
        after = os.fstat(stream.fileno())
        if (after.st_size, after.st_mtime_ns) != (opened.st_size, opened.st_mtime_ns):
            raise ValueError("file changed")
        if len(body) > limit:
            raise OverflowError("too large")
        return body


def content_findings(name: str, body: bytes) -> list[dict]:
    findings = []
    # Text with a UTF-16 BOM is inspected as normalized UTF-8 as well as raw bytes.
    texts = [body]
    if body.startswith((b"\xff\xfe", b"\xfe\xff")):
        try:
            texts.append(body.decode("utf-16").encode("utf-8"))
        except UnicodeError:
            findings.append({"path": name, "rule": "malformed_text_encoding", "count": 1, "line": None})
    for rule, pattern in CONTENT_RULES:
        for candidate in texts:
            matches = list(pattern.finditer(candidate))
            if matches:
                findings.append({"path": name, "rule": rule, "count": len(matches),
                                 "line": candidate.count(b"\n", 0, matches[0].start()) + 1})
                break
    if body.startswith(b"version https://git-lfs.github.com/spec/v1"):
        findings.append({"path": name, "rule": "unmaterialized_lfs_pointer", "count": 1, "line": 1})
    return findings


def scan_submission(root: Path | str, manifest: object, *, max_file_bytes: int = DEFAULT_MAX_FILE_BYTES) -> dict:
    report = {"protocol": PROTOCOL, "scope": "explicit-selected-files-only",
              "passed": False, "selected_files": 0, "inspected_files": 0,
              "inspected_bytes": 0, "max_file_bytes": max_file_bytes, "findings": [],
              "limits": ["No licensing approval", "No semantic personal-data review",
                         "No Git-history audit", "No decompression or embedded-document inspection"]}

    def fail(path, rule):
        report["findings"].append({"path": path, "rule": rule, "count": 1, "line": None})

    if type(max_file_bytes) is not int or max_file_bytes <= 0:
        fail("<configuration>", "invalid_size_limit")
        return report
    root = Path(root).absolute()
    try:
        _no_links(root)
        if not root.is_dir():
            raise ValueError("root is not a directory")
        root = root.resolve(strict=True)
    except (OSError, ValueError):
        fail("<root>", "invalid_or_linked_root")
        return report
    if not isinstance(manifest, dict) or not isinstance(manifest.get("files"), list) or not manifest["files"]:
        fail("<manifest>", "invalid_or_empty_file_list")
        return report
    rows = manifest["files"]
    report["selected_files"] = len(rows)
    seen = set()
    accepted = []
    for i, row in enumerate(rows, 1):
        label = _label(row.get("path") if isinstance(row, dict) else None, i)
        if not isinstance(row, dict) or not {"path", "sha256", "bytes"}.issubset(row):
            fail(label, "invalid_manifest_entry")
            continue
        try:
            name = relative_name(row["path"])
        except ValueError:
            fail(label, "unsafe_relative_path")
            continue
        normalized = unicodedata.normalize("NFKC", name).casefold()
        if normalized in seen:
            fail(label, "duplicate_or_colliding_path")
            continue
        seen.add(normalized)
        if blocked_path(name):
            fail(label, "excluded_private_or_runtime_path")
            continue
        if (type(row["bytes"]) is not int or row["bytes"] < 0
                or not isinstance(row["sha256"], str)
                or re.fullmatch(r"[0-9a-f]{64}", row["sha256"]) is None):
            fail(label, "invalid_size_or_digest")
            continue
        if row["bytes"] > max_file_bytes:
            fail(label, "file_too_large")
            continue
        accepted.append((name, label, row))
    for name, label, row in accepted:
        try:
            body = _read_checked(root, name, max_file_bytes)
        except FileNotFoundError:
            fail(label, "missing_file")
            continue
        except OverflowError:
            fail(label, "file_too_large")
            continue
        except (OSError, ValueError):
            fail(label, "unreadable_linked_or_changed_file")
            continue
        report["inspected_files"] += 1
        report["inspected_bytes"] += len(body)
        if len(body) != row["bytes"]:
            fail(label, "size_mismatch")
        if hashlib.sha256(body).hexdigest() != row["sha256"]:
            fail(label, "sha256_mismatch")
        report["findings"].extend(content_findings(label, body))
    report["passed"] = not report["findings"]
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--max-file-bytes", type=int, default=DEFAULT_MAX_FILE_BYTES)
    args = parser.parse_args(argv)
    try:
        _no_links(args.manifest.absolute())
        if args.manifest.stat().st_size > DEFAULT_MAX_FILE_BYTES:
            raise ValueError("oversized manifest")
        manifest = strict_json(args.manifest.read_bytes())
    except (OSError, ValueError, UnicodeError):
        manifest = None
    report = scan_submission(args.root, manifest, max_file_bytes=args.max_file_bytes)
    encoded = json.dumps(report, indent=2, ensure_ascii=True) + "\n"
    if args.output is not None:
        # Never overwrite an input, prior audit, or selected delivery file.
        try:
            _no_links(args.output.absolute().parent)
            with args.output.open("x", encoding="utf-8") as stream:
                stream.write(encoded)
        except (OSError, ValueError):
            report["passed"] = False
            report["findings"].append({"path": "<report>", "rule": "report_write_refused", "count": 1, "line": None})
            encoded = json.dumps(report, indent=2, ensure_ascii=True) + "\n"
    sys.stdout.write(encoded)
    return 0 if report["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
