# SPDX-License-Identifier: GPL-3.0-only
from pathlib import Path
import tempfile
import unittest
from tools.collect_action_diagnostics import captured_files

class CapturedDiagnostics(unittest.TestCase):
    def test_allowlist_budget_and_secret_line_filter(self):
        with tempfile.TemporaryDirectory() as root:
            p=Path(root)
            (p/'unrelated.txt').write_text('must not be published')
            (p/'emulator-host.txt').write_text('KVM enabled\nAuthorization: hidden\nhttps://example.test/?sig=hidden\n'+'x'*20000)
            rows=captured_files(p)
            self.assertEqual(len(rows),1)
            self.assertEqual(rows[0]['path'],'emulator-host.txt')
            self.assertTrue(rows[0]['text'].startswith('KVM enabled\n'))
            self.assertNotIn('hidden',rows[0]['text'])
            self.assertLessEqual(len(rows[0]['text']),16000)

    def test_maximum_file_count(self):
        with tempfile.TemporaryDirectory() as root:
            p=Path(root)
            for i in range(10):
                d=p/str(i);d.mkdir();(d/'boot-tail.txt').write_text('boot')
            self.assertEqual(len(captured_files(p)),8)

    def test_junit_failure_is_available_without_binary_artifacts(self):
        with tempfile.TemporaryDirectory() as root:
            p=Path(root)
            (p/'TEST-instrumentation.xml').write_text('<failure>Activity not found</failure>')
            (p/'unrelated.xml').write_text('not allowed')
            rows=captured_files(p)
            self.assertEqual(len(rows),1)
            self.assertEqual(rows[0]['text'],'<failure>Activity not found</failure>')
