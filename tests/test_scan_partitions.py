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

class ModuleTests(unittest.TestCase):
    def test_config_services_not_executed(self):
        from unittest.mock import patch
        from tools.scan_partitions import inspect_configs
        entry = {'kind': 'file', 'path': '/etc/init/test.rc', 'inode': 1, 'size_bytes': 100}
        text = ('service tracking /odm/bin/trackingservice\n'
                '    class main\n    user system\n    group system graphics\n'
                'on boot\n    exec /do/not/execute\n')
        def dump(image, entry, output):
            output.write_text(text)
        with patch('tools.scan_partitions.dump_entry', side_effect=dump):
            results = inspect_configs(Path('fixture'), [entry])
        service = results[0]['services'][0]
        self.assertEqual(service['name'], 'tracking')
        self.assertEqual(service['command'], ['/odm/bin/trackingservice'])
        self.assertNotIn('exec', str(service))

    def test_build_properties_filter(self):
        from unittest.mock import patch
        from tools.scan_partitions import inspect_configs
        entry = {'kind': 'file', 'path': '/build.prop', 'inode': 1, 'size_bytes': 100}
        def dump(image, entry, output):
            output.write_text('ro.build.id=fixture\nunrelated.secret=not_reported\n')
        with patch('tools.scan_partitions.dump_entry', side_effect=dump):
            result = inspect_configs(Path('fixture'), [entry])[0]
        self.assertEqual(result['build_properties'], {'ro.build.id': 'fixture'})

    def test_apex_payload_is_read_not_executed(self):
        import zipfile
        from unittest.mock import patch
        from tools.scan_partitions import inspect_apex
        entry = {'kind': 'file', 'path': '/apex/com.meta.fixture.apex', 'inode': 1, 'size_bytes': 4096}
        def dump(image, entry, output):
            with zipfile.ZipFile(output, 'w') as z:
                z.writestr('apex_payload.img', b'non-ext4 test fixture')
                z.writestr('../../do-not-extract', b'ignored')
        with patch('tools.scan_partitions.dump_entry', side_effect=dump):
            result = inspect_apex(Path('fixture'), [entry])[0]
        self.assertEqual(result['status'], 'PAYLOAD_INSPECTED')
        self.assertEqual(result['inventory']['status'], 'UNSUPPORTED_FILESYSTEM')
        self.assertFalse(result['signature_verified'])

    def test_apex_duplicate_names_refused(self):
        import warnings
        import zipfile
        from unittest.mock import patch
        from tools.scan_partitions import inspect_apex
        entry = {'kind': 'file', 'path': '/apex/com.meta.fixture.apex', 'inode': 1, 'size_bytes': 4096}
        def dump(image, entry, output):
            with warnings.catch_warnings():
                warnings.simplefilter('ignore', UserWarning)
                with zipfile.ZipFile(output, 'w') as z:
                    z.writestr('apex_payload.img', b'a')
                    z.writestr('apex_payload.img', b'b')
        with patch('tools.scan_partitions.dump_entry', side_effect=dump):
            result = inspect_apex(Path('fixture'), [entry])[0]
        self.assertEqual(result['status'], 'APEX_ANALYSIS_FAILED')
        self.assertIn('Duplicate', result['error'])
