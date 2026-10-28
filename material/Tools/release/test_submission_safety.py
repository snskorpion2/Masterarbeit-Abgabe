"""Synthetic-only safety checks; no repository credentials or research outputs."""
import contextlib
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

_PATH = Path(__file__).with_name("check_submission_safety.py")
_SPEC = importlib.util.spec_from_file_location("submission_safety", _PATH)
safety = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(safety)


class SubmissionSafetyTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def file(self, name="data/result.json", body=b'{"score":0.5}\n'):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(body)
        return {"path": name, "sha256": hashlib.sha256(body).hexdigest(), "bytes": len(body)}

    def scan(self, rows, **kwargs):
        return safety.scan_submission(self.root, {"files": rows}, **kwargs)

    def rules(self, result):
        return {r["rule"] for r in result["findings"]}

    def test_clean_numeric_file_passes_and_is_bound(self):
        row = self.file()
        result = self.scan([row])
        self.assertTrue(result["passed"])
        self.assertEqual(result["inspected_files"], 1)
        self.assertEqual(result["inspected_bytes"], row["bytes"])

    def test_unselected_file_is_not_opened(self):
        row = self.file()
        self.file("unselected.txt", b"not part of selected delivery")
        self.assertEqual(self.scan([row])["inspected_files"], 1)

    def test_no_empty_or_ambiguous_manifest(self):
        for manifest in (None, {}, {"files": []}, {"files": "all"}):
            with self.subTest(manifest=manifest):
                self.assertFalse(safety.scan_submission(self.root, manifest)["passed"])
        for raw in (b'{"files":[],"files":[]}', b'{"files":[NaN]}'):
            with self.assertRaises(ValueError):
                safety.strict_json(raw)

    def test_missing_file(self):
        row = self.file()
        (self.root / row["path"]).unlink()
        self.assertIn("missing_file", self.rules(self.scan([row])))

    def test_size_and_digest_mismatch_both_reported(self):
        row = self.file()
        (self.root / row["path"]).write_bytes(b"changed")
        self.assertEqual(self.rules(self.scan([row])), {"size_mismatch", "sha256_mismatch"})

    def test_manifest_digest_and_size_types_are_strict(self):
        for change in ({"bytes": True}, {"bytes": -1}, {"sha256": "A" * 64}, {"sha256": None}):
            self.assertIn("invalid_size_or_digest", self.rules(self.scan([{**self.file(), **change}])))

    def test_duplicate_case_and_unicode_collisions(self):
        for names in (("a.json", "a.json"), ("A.json", "a.json"), ("\u00e9.json", "e\u0301.json")):
            with self.subTest(names=names):
                rows = [self.file(n) for n in names]
                self.assertIn("duplicate_or_colliding_path", self.rules(self.scan(rows)))

    def test_traversal_and_nonportable_paths_are_masked(self):
        examples = ["../private.txt", "/" + "home" + "/person/file",
                    "C:" + "/" + "Users" + "/person/file", "F:" + "\\source\\repo",
                    "//server/share", "a/../b", "a//b", "a/./b", "a ", "aux.txt", "a\x00b", "a?.txt", "a\ud800b", "a\u202eb"]
        for name in examples:
            with self.subTest(name=name):
                row = {**self.file(), "path": name}
                result = self.scan([row])
                self.assertIn("unsafe_relative_path", self.rules(result))
                self.assertEqual(result["findings"][0]["path"], "<entry:1>")

    def test_excluded_paths(self):
        for name in (".env", ".env.local", ".git/config", "private/file.json", "gold_sealed.json", "a/gold/data.json", "models/checkpoint.bin", "a/runtime/file.py", "response.raw", "raw.json", "gold_sealed.jsonl", "data.private.json", "a/" + "AppData" + "/file.txt"):
            with self.subTest(name=name):
                row = {**self.file(), "path": name}
                self.assertIn("excluded_private_or_runtime_path", self.rules(self.scan([row])))

    def test_runtime_source_allowed_but_runtime_directory_and_sensitive_data_blocked(self):
        source = self.file("Tools/experiments/fair_tail_oct23_v1/runtime.py", b"def run():\n    return 1\n")
        self.assertTrue(self.scan([source])["passed"])
        for name in ("Tools/experiments/runtime/helper.py", "results/gold.csv", "results/raw.jsonl",
                     "results/private.yaml", "results/runtime.json"):
            with self.subTest(name=name):
                self.assertIn("excluded_private_or_runtime_path", self.rules(self.scan([{**source, "path": name}])))

    def test_size_bound_applies_to_actual_and_declared_size(self):
        row = self.file(body=b"x" * 20)
        self.assertIn("file_too_large", self.rules(self.scan([row], max_file_bytes=10)))
        self.assertIn("file_too_large", self.rules(self.scan([{**row, "bytes": 5}], max_file_bytes=10)))
        self.assertIn("invalid_size_limit", self.rules(self.scan([row], max_file_bytes=False)))

    def test_lfs_pointer_is_not_a_deliverable(self):
        body = b"version https://git-lfs.github.com/spec/v1\n" + b"oid sha256:" + b"0" * 64 + b"\nsize 10\n"
        self.assertIn("unmaterialized_lfs_pointer", self.rules(self.scan([self.file(body=body)])))

    def test_private_paths_in_raw_json_and_utf16_text(self):
        values = ["C:" + "/" + "Users" + "/person/file", "F:" + "/source/repo/file",
                  "C:" + "\\Users\\person\\file", "/" + "home" + "/person/file",
                  "/" + "Users" + "/person/file", "AppData" + "/Local/cache",
                  "Masterarbeit-private-evidence" + "/source"]
        for value in values:
            for body in (value.encode(), json.dumps({"path": value}).encode(), value.encode("utf-16")):
                with self.subTest(value=value, encoding=body[:2]):
                    result = self.scan([self.file(body=body)])
                    self.assertFalse(result["passed"])
                    self.assertTrue(any(x.startswith("private_") for x in self.rules(result)))
                    self.assertNotIn(value, json.dumps(result))

    def test_synthetic_credential_formats_and_never_echo_values(self):
        # Build examples at runtime so the test source is itself deliverable.
        examples = [
            (b"AK" + b"IA" + b"Z" * 16, "aws_access_key"),
            (b"sk" + b"-proj-" + b"A" * 32, "provider_api_key"),
            (b"gh" + b"p_" + b"A" * 30, "github_token"),
            (b"h" + b"f_" + b"A" * 35, "huggingface_token"),
            (b"Bearer " + b"A" * 30, "bearer_credential"),
            (b"?sv=x&sig=" + b"B" * 30, "azure_sas_signature"),
            (b'api_key = "' + b"C" * 32 + b'"', "literal_secret_assignment"),
            (b'"azure_api_key": "' + b"D" * 32 + b'"', "literal_secret_assignment"),
            (b'aws_secret_access_key="' + b"E" * 40 + b'"', "literal_secret_assignment"),
            (b'export AZURE_API_KEY=' + b"F" * 32, "unquoted_secret_assignment"),
            (b'api_key: ' + b"G" * 32, "unquoted_secret_assignment"),
            (b"-----BEGIN " + b"PRIVATE KEY-----\n", "private_key_material"),
        ]
        for body, expected in examples:
            with self.subTest(expected=expected):
                result = self.scan([self.file(body=b"first line\n" + body)])
                self.assertIn(expected, self.rules(result))
                finding = next(f for f in result["findings"] if f["rule"] == expected)
                self.assertEqual(finding["line"], 2)
                self.assertNotIn(body.decode(), json.dumps(result))
                self.assertEqual(set(finding), {"path", "rule", "count", "line"})

    def test_environment_access_and_pattern_source_are_not_hardcoded_keys(self):
        body = b'api_key = os.getenv("API_KEY")\nsecret = load_secret()\n'
        self.assertTrue(self.scan([self.file(body=body)])["passed"])
        self.assertEqual(safety.content_findings("checker.py", _PATH.read_bytes()), [])
        self.assertEqual(safety.content_findings("test_checker.py", Path(__file__).read_bytes()), [])

    def test_source_code_with_actual_hardcoded_key_is_still_rejected(self):
        payload = b'api_key="' + b"Q" * 32 + b'"\n'
        result = self.scan([self.file("code/main.py", payload)])
        self.assertIn("literal_secret_assignment", self.rules(result))

    def test_leaf_and_parent_symlink_rejected(self):
        target = self.root / "real"
        target.mkdir()
        (target / "x.txt").write_bytes(b"safe")
        for dirname in (False, True):
            link = self.root / ("linked_dir" if dirname else "linked.txt")
            try:
                link.symlink_to(target if dirname else target/"x.txt", target_is_directory=dirname)
            except (OSError, NotImplementedError):
                self.skipTest("OS does not permit creating symlinks")
            name = "linked_dir/x.txt" if dirname else "linked.txt"
            row = {"path": name, "bytes": 4, "sha256": hashlib.sha256(b"safe").hexdigest()}
            self.assertIn("unreadable_linked_or_changed_file", self.rules(self.scan([row])))

    def test_cli_report_is_exclusive_and_has_same_safe_payload(self):
        manifest = self.root / "manifest.json"
        manifest.write_text(json.dumps({"files": [self.file()]}), encoding="utf-8")
        output = self.root / "audit.json"
        buf = io.StringIO()
        args = ["--root", str(self.root), "--manifest", str(manifest), "--output", str(output)]
        with contextlib.redirect_stdout(buf):
            self.assertEqual(safety.main(args), 0)
        self.assertEqual(json.loads(buf.getvalue()), json.loads(output.read_text()))
        before = output.read_bytes()
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(safety.main(args), 2)
        self.assertEqual(output.read_bytes(), before)

    def test_cli_exit_two_and_no_credential_leak(self):
        value = "Z" * 32
        row = self.file(body=('api_key="' + value + '"').encode())
        manifest = self.root / "manifest.json"
        manifest.write_text(json.dumps({"files": [row]}), encoding="utf-8")
        result = subprocess.run([sys.executable, "-B", str(_PATH), "--root", str(self.root), "--manifest", str(manifest)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 2)
        self.assertNotIn(value, result.stdout + result.stderr)
        self.assertFalse(json.loads(result.stdout)["passed"])


if __name__ == "__main__":
    unittest.main()
