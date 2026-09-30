import hashlib
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from tools.inventory import inventory


class InventoryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / "sample.bin").write_bytes(b"test fixture, not Horizon OS")

    def test_hash_and_explicit_unverified_status(self):
        for version in ("v2.4", "v2.7"):
            report = inventory(self.root, version, "fixture")
            self.assertEqual(report["version_verification"], "UNVERIFIED")
            self.assertEqual(report["port_status"], "NOT PORTED YET")
            entry = report["files"][0]
            data = (self.root / "sample.bin").read_bytes()
            self.assertEqual(entry["sha256"], hashlib.sha256(data).hexdigest())
            self.assertEqual(entry["size_bytes"], len(data))

    def test_reject_other_versions(self):
        for version in ("v2.3", "v2.5", "v2.6", "v2.8", "unknown", "v2.7-beta", ""):
            with self.assertRaises(ValueError):
                inventory(self.root, version, "fixture")

    def test_provenance_required(self):
        with self.assertRaises(ValueError):
            inventory(self.root, "v2.4", " ")

    def test_reject_symlinks(self):
        for target in (self.root / "sample.bin", self.root, self.root / "missing"):
            link = self.root / "link"
            link.symlink_to(target)
            with self.assertRaises(ValueError):
                inventory(self.root, "v2.4", "fixture")
            link.unlink()

    def test_reject_special_file(self):
        os.mkfifo(self.root / "pipe")
        with self.assertRaises(ValueError):
            inventory(self.root, "v2.4", "fixture")

    def test_reject_empty_directory(self):
        (self.root / "sample.bin").unlink()
        with self.assertRaises(ValueError):
            inventory(self.root, "v2.4", "fixture")

    def test_deterministic_nested_inventory(self):
        (self.root / "nested").mkdir()
        (self.root / "nested" / "a.bin").write_bytes(b"a")
        first = inventory(self.root, "v2.7", "fixture")
        self.assertEqual(first, inventory(self.root, "v2.7", "fixture"))
        self.assertEqual([e["path"] for e in first["files"]],
                         ["nested/a.bin", "sample.bin"])

    def test_cli_out_of_scope_no_report(self):
        result = subprocess.run([sys.executable, "tools/inventory.py", "--version", "v2.8",
                                 "--artifacts", str(self.root), "--provenance", "fixture"],
                                capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(result.stdout, "")


if __name__ == "__main__":
    unittest.main()
