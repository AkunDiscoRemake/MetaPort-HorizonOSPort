import hashlib
from pathlib import Path
import tempfile
import unittest
import zipfile
from tools.inspect_ota import inspect, LIMIT


class OtaTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "fixture.zip"

    def make(self, text):
        with zipfile.ZipFile(self.path, "w") as z:
            z.writestr("META-INF/com/android/metadata", text)
            z.writestr("payload.bin", b"test fixture only")
        return hashlib.sha256(self.path.read_bytes()).hexdigest()

    def test_bounded_metadata_not_firmware(self):
        digest = self.make("ota-type=AB\npost-build=test\n")
        result = inspect(self.path, digest)
        self.assertEqual(result["metadata"]["META-INF/com/android/metadata"]["ota-type"], "AB")
        self.assertEqual(result["full_image"], "UNVERIFIED")
        self.assertEqual(result["stable_channel"], "UNVERIFIED")
        self.assertEqual(list(self.path.parent.iterdir()), [self.path])

    def test_wrong_hash(self):
        self.make("ota-type=AB")
        with self.assertRaisesRegex(ValueError, "SHA-256"):
            inspect(self.path)

    def test_incremental_requirement(self):
        digest = self.make("pre-build-incremental=123\n")
        self.assertTrue(inspect(self.path, digest)["incremental_base_declared"])

    def test_oversized_metadata(self):
        digest = self.make("x=" + "a" * LIMIT)
        with self.assertRaisesRegex(ValueError, "size limit"):
            inspect(self.path, digest)

    def test_duplicate_key(self):
        digest = self.make("ota-type=AB\nota-type=BLOCK")
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            inspect(self.path, digest)
