"""Pruefung und synthetischer CPU-Nachvollzug der elektronischen Beilage."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from urllib.parse import unquote, urlsplit

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "material"))
from Tools.release.check_submission_safety import (  # noqa: E402
    _read_checked, content_findings, relative_name, scan_submission, strict_json,
)


def actual_files(root: Path) -> tuple[set[str], int]:
    """Inspect the delivered tree, also without a Git checkout."""
    names, linked = set(), 0
    for current, dirs, files in os.walk(root, followlinks=False):
        current = Path(current)
        if current == root:
            dirs[:] = [name for name in dirs if name != ".git"]
            files = [name for name in files if name != ".git"]
        for name in list(dirs):
            if (current / name).is_symlink():
                linked += 1
                dirs.remove(name)
        for name in files:
            path = current / name
            linked += path.is_symlink()
            names.add(path.relative_to(root).as_posix())
    return names, linked


def documentation_links(root: Path) -> dict:
    """Check current navigation; historical reports retain their old references."""
    paths = [root / "README.md", *sorted((root / "docs").glob("*.md"))]
    checked, invalid = 0, 0
    for path in paths:
        text = path.read_text(encoding="utf-8")
        for target in re.findall(r"\]\(([^)]+)\)", text):
            target = target.strip().strip("<>")
            parts = urlsplit(target)
            if parts.scheme or parts.netloc or not parts.path:
                continue
            checked += 1
            resolved = (path.parent / unquote(parts.path)).resolve()
            if not resolved.is_relative_to(root) or not resolved.exists():
                invalid += 1
    return {"checked": checked, "invalid": invalid}


def audit(root: Path = ROOT) -> dict:
    root = root.resolve()
    outer_raw = _read_checked(root, "MANIFEST.json", 25 * 1024 * 1024)
    outer = strict_json(outer_raw)
    delivered = scan_submission(root, outer)
    manifest_findings = content_findings("MANIFEST.json", outer_raw)
    inner = strict_json(_read_checked(root, "material/MANIFEST.json", 25 * 1024 * 1024))
    material = scan_submission(root / "material", inner)
    expected = {row["path"] for row in outer["files"]} | {"MANIFEST.json"}
    actual, linked = actual_files(root)
    links = documentation_links(root)
    return {
        "protocol": "structured-submission-check-v1",
        "passed": (delivered["passed"] and material["passed"]
                   and not manifest_findings and expected == actual
                   and linked == 0 and links["invalid"] == 0),
        "outer": delivered,
        "inner": material,
        "manifest_content_findings": manifest_findings,
        "inventory": {"expected": len(expected), "actual": len(actual),
                      "missing": len(expected - actual), "unlisted": len(actual - expected),
                      "linked": linked},
        "documentation_links": links,
    }


def refresh_outer_manifest(root: Path, additional_paths=()) -> None:
    """Rebind an explicit selection after an authorized package update.

    The finalization tool calls this after updating the inner provenance and
    manifest. Unlisted files are never discovered or silently selected.
    """
    root = root.resolve()
    manifest = strict_json(_read_checked(root, "MANIFEST.json", 25 * 1024 * 1024))
    entries = {row["path"]: row for row in manifest["files"]}
    for name in additional_paths:
        name = relative_name(name)
        if name == "MANIFEST.json":
            raise ValueError("Manifest cannot bind itself")
        entries.setdefault(name, {"path": name, "category": "explicit_finalization_addition"})
    for name, entry in entries.items():
        body = _read_checked(root, name, 25 * 1024 * 1024)
        entry["bytes"] = len(body)
        entry["sha256"] = hashlib.sha256(body).hexdigest()
    manifest["files"] = [entries[name] for name in sorted(entries)]
    manifest["total_selected_bytes"] = sum(entry["bytes"] for entry in manifest["files"])
    encoded = (json.dumps(manifest, ensure_ascii=True, indent=2) + "\n").encode("utf-8")
    (root / "MANIFEST.json").write_bytes(encoded)


def demo_output(value: Path) -> Path:
    target = value.resolve()
    if target.is_relative_to(ROOT):
        raise ValueError("Choose a new output directory outside the delivered package")
    if target.exists():
        raise FileExistsError("Choose a new output directory")
    return target


def run_tests() -> int:
    commands = [
        (ROOT / "material", ["-m", "unittest", "Tools.release.test_submission_safety", "-q"]),
        (ROOT, ["-m", "unittest", "test_reproduktion", "-q"]),
    ]
    for cwd, command in commands:
        result = subprocess.run([sys.executable, "-B", "-X", "utf8", *command], cwd=cwd)
        if result.returncode:
            return result.returncode
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("pruefen", help="Lieferbaum, Hashes und Navigation pruefen")
    commands.add_parser("tests", help="Unterstuetzte Pakettests ausfuehren")
    demo = commands.add_parser("demo", help="Synthetische Auswertung ohne Modellaufrufe")
    demo.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    report = audit()
    if args.command == "pruefen" or not report["passed"]:
        print(json.dumps(report, ensure_ascii=True, indent=2))
    if not report["passed"]:
        return 2
    if args.command == "tests":
        return run_tests()
    if args.command == "demo":
        target = demo_output(args.output)
        return subprocess.run([
            sys.executable, "-B", "-X", "utf8", "Tools/release/submission_cpu.py",
            "--output", str(target),
        ], cwd=ROOT / "material").returncode
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
