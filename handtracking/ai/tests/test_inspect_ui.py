from pathlib import Path
import tempfile
import unittest
from handtracking.ai.inspect_ui import summarize_sources

class UiSummaryTests(unittest.TestCase):
    def test_decompiler_failures_are_not_successful_source_recovery(self):
        with tempfile.TemporaryDirectory() as root:
            path=Path(root)/'Shell.java'
            path.write_text('class Shell { native void onHandPose(int id);\n// JADX ERROR\n// Method not decompiled:\n}')
            report=summarize_sources(root)
            self.assertEqual(report['generated_java_files'],1)
            self.assertEqual(report['files_with_decompiler_errors'],1)
            self.assertEqual(report['native_declarations_total'],1)
            self.assertFalse(report['runtime_validated'])
            self.assertTrue(report['contracts'][0]['has_decompiler_errors'])
