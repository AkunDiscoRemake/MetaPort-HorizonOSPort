# SPDX-License-Identifier: GPL-3.0-only
import tempfile
from pathlib import Path
import unittest
from tools.summarize_android_runtime import summarize, EXPECTED_CASES

class RuntimeReportTests(unittest.TestCase):
    def fixture(self,root,extra=''):
        cases=''.join(f'<testcase classname="org.metaport.port.AdapterRuntimeTest" name="{name}">{extra}</testcase>' for name in sorted(EXPECTED_CASES))
        (root/'TEST-fixture.xml').write_text('<testsuite tests="5">'+cases+'</testsuite>')
    def test_requires_executed_cases(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)
            with self.assertRaises(ValueError):summarize(p,29)
            self.fixture(p)
            r=summarize(p,29);self.assertTrue(r['passed'])
            self.assertFalse(r['original_firmware_executed'])
            self.assertFalse(r['physical_device_tested'])
    def test_skip_failure_and_duplicates_cannot_pass(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)
            for extra in ('<skipped/>','<failure/>','<error/>'):
                self.fixture(p,extra);self.assertFalse(summarize(p,35)['passed'])
            self.fixture(p)
            (p/'TEST-copy.xml').write_bytes((p/'TEST-fixture.xml').read_bytes())
            self.assertFalse(summarize(p,35)['passed'])
    def test_suite_error_cannot_be_hidden_by_passing_cases(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d);self.fixture(p)
            f=p/'TEST-fixture.xml';f.write_text(f.read_text().replace('tests="5"','tests="5" errors="1"'))
            with self.assertRaises(ValueError):summarize(p,29)

    def test_expected_cases_match_instrumented_methods(self):
        import re
        root=Path(__file__).resolve().parents[1]
        source=(root/'port/android/adapters/src/androidTest/java/org/metaport/port/AdapterRuntimeTest.java').read_text()
        names=set(re.findall(r'@Test\(timeout=120000\) public void (\w+)',source))
        self.assertEqual(names,EXPECTED_CASES)
