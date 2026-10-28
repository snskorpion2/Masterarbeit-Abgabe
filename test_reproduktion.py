"""Finite controls for the delivered package envelope."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

import reproduzieren as package


def encoded(value):
    return (json.dumps(value, indent=2) + "\n").encode()


class PackageControls(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / "material").mkdir()
        (self.root / "docs").mkdir()
        (self.root / "material/value.txt").write_bytes(b"finite synthetic fixture\n")
        (self.root / "README.md").write_text("[value](material/value.txt)\n", encoding="utf-8")
        inner = {"files": [self.entry("material/value.txt", prefix="material/")]}
        (self.root / "material/MANIFEST.json").write_bytes(encoded(inner))
        outer = {"files": [self.entry(name) for name in
                          ["README.md", "material/value.txt", "material/MANIFEST.json"]]}
        (self.root / "MANIFEST.json").write_bytes(encoded(outer))

    def entry(self, name, prefix=""):
        body = (self.root / name).read_bytes()
        return {"path": name.removeprefix(prefix), "bytes": len(body),
                "sha256": hashlib.sha256(body).hexdigest()}

    def test_clean_tree_without_git_is_supported(self):
        self.assertTrue(package.audit(self.root)["passed"])

    def test_unlisted_file_blocks_full_package_even_if_scanners_pass(self):
        (self.root / "extra.txt").write_bytes(b"not selected\n")
        report = package.audit(self.root)
        self.assertTrue(report["outer"]["passed"])
        self.assertFalse(report["passed"])
        self.assertEqual(report["inventory"]["unlisted"], 1)

    def test_changed_inner_bytes_fail_both_bindings(self):
        (self.root / "material/value.txt").write_bytes(b"changed\n")
        report = package.audit(self.root)
        self.assertFalse(report["outer"]["passed"])
        self.assertFalse(report["inner"]["passed"])
        self.assertFalse(report["passed"])

    def test_broken_navigation_is_reported_after_explicit_hash_update(self):
        (self.root / "README.md").write_text("[missing](missing.txt)\n", encoding="utf-8")
        package.refresh_outer_manifest(self.root)
        report = package.audit(self.root)
        self.assertTrue(report["outer"]["passed"])
        self.assertFalse(report["passed"])
        self.assertEqual(report["documentation_links"]["invalid"], 1)

    def test_outer_refresh_does_not_approve_changed_inner_binding(self):
        (self.root / "material/value.txt").write_bytes(b"changed\n")
        package.refresh_outer_manifest(self.root)
        report = package.audit(self.root)
        self.assertTrue(report["outer"]["passed"])
        self.assertFalse(report["inner"]["passed"])
        self.assertFalse(report["passed"])


if __name__ == "__main__":
    unittest.main()
