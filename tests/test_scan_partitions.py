import shutil
from pathlib import Path
import subprocess
import tempfile
import unittest
from tools.scan_partitions import scan, elf_report, list_ext4


class ScanTests(unittest.TestCase):
    def test_unsupported_is_explicit(self):
        self.assertEqual(scan(Path('nonexistent'), 'erofs')['status'], 'UNSUPPORTED_FILESYSTEM')

    def test_non_elf(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'file'
            path.write_bytes(b'not executable')
            self.assertEqual(elf_report(path)['format'], 'NOT_ELF')

    @unittest.skipUnless(shutil.which('debugfs') and shutil.which('mke2fs'), 'ext4 host tools unavailable')
    def test_real_ext4_inventory_without_mount(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            content = root / 'content'
            content.mkdir()
            (content / 'build.prop').write_text('test.fixture=true\n')
            (content / 'link').symlink_to('build.prop')
            image = root / 'fixture.img'
            with image.open('wb') as stream:
                stream.truncate(16 * 1024 * 1024)
            subprocess.run(['mke2fs', '-q', '-t', 'ext4', '-d', str(content), str(image)], check=True,
                           capture_output=True)
            entries = {entry['path']: entry for entry in list_ext4(image)}
            self.assertEqual(entries['/build.prop']['kind'], 'file')
            self.assertEqual(entries['/link']['kind'], 'symlink')
            self.assertEqual(entries['/build.prop']['size_bytes'], 18)

    @unittest.skipUnless(shutil.which('readelf'), 'readelf unavailable')
    def test_host_elf_read_only(self):
        path = shutil.which('true')
        if not path:
            self.skipTest('ELF fixture unavailable')
        report = elf_report(Path(path))
        self.assertEqual(report['format'], 'ELF')
        self.assertIn('machine', report)
        self.assertIn('needed', report)
