# SPDX-License-Identifier: GPL-3.0-only
import tempfile
from pathlib import Path
import unittest
from tools.summarize_android_runtime import summarize, EXPECTED_CASES, EXPECTED_TESTS, SERVICE_CASES

class RuntimeReportTests(unittest.TestCase):
    def fixture(self,root,extra=''):
        cases=''.join(f'<testcase classname="{owner}" name="{name}">{extra}</testcase>' for owner,name in sorted(EXPECTED_TESTS))
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
            r=summarize(p,29)
            self.assertFalse(r['passed']);self.assertTrue(r['suite_failed'])
            self.assertEqual(len(r['tests']),len(EXPECTED_TESTS))

    def test_expected_cases_match_instrumented_methods(self):
        import re
        root=Path(__file__).resolve().parents[1]
        source=(root/'port/android/adapters/src/androidTest/java/org/metaport/port/AdapterRuntimeTest.java').read_text()
        names=set(re.findall(r'@Test\(timeout=120000\) public void (\w+)',source))
        self.assertEqual(names,EXPECTED_CASES)

    def test_service_cases_match_instrumented_methods(self):
        import re
        root=Path(__file__).resolve().parents[1]
        source=(root/'port/android/adapters/src/androidTest/java/org/metaport/port/services/ServiceDirectoryTest.java').read_text()
        self.assertEqual(set(re.findall(r'@Test public void (\w+)',source)),SERVICE_CASES)

    def test_wrong_owner_or_missing_transport_case_cannot_pass(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d);self.fixture(p)
            f=p/'TEST-fixture.xml'
            f.write_text(f.read_text().replace('org.metaport.port.services.ServiceDirectoryTest','org.metaport.port.AdapterRuntimeTest'))
            self.assertFalse(summarize(p,35)['passed'])

    def test_window_cases_match_instrumented_methods(self):
        import re
        from tools.summarize_android_runtime import WINDOW_CASES
        root=Path(__file__).resolve().parents[1]
        source=(root/'port/android/adapters/src/androidTest/java/org/metaport/port/focus/AppWindowFocusBackendTest.java').read_text()
        self.assertEqual(set(re.findall(r'@Test\(timeout=120000\) public void (\w+)',source)),WINDOW_CASES)

    def test_failure_details_survive_suite_failure_and_are_bounded(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d);self.fixture(p,'<failure>'+'x'*9000+'</failure>')
            f=p/'TEST-fixture.xml';f.write_text(f.read_text().replace('tests="5"','tests="5" failures="12"'))
            r=summarize(p,29)
            self.assertFalse(r['passed']);self.assertTrue(r['suite_failed'])
            self.assertEqual(len(r['tests']),len(EXPECTED_TESTS))
            self.assertEqual(r['tests'][0]['failure_detail'],'x'*8192)
