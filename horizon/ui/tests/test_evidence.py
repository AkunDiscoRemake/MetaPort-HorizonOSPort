import tempfile
from pathlib import Path
import unittest
from horizon.ui.evidence import summarize_ux, LIMIT

class EvidenceTests(unittest.TestCase):
    def test_separate_categories_and_errors(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d)
            (p/'Shell.java').write_text('// JADX ERROR\nPassthrough.start();\nSurfaceControl.x();\nValueAnimator.x();')
            (p/'layout.xml').write_text('<layout/>')
            r = summarize_ux(p)
            self.assertFalse(r['ui_ported'])
            self.assertEqual(r['resource_files_total'], 1)
            for k in ('passthrough', 'composition', 'ux_animation'):
                self.assertEqual(r['categories'][k]['matching_lines'], 1)
                self.assertTrue(r['categories'][k]['sites'][0]['has_decompiler_errors'])
    def test_counts_continue_after_bounded_sample(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d)/'Shell.java').write_text('passthrough();\n'*(LIMIT+3))
            r=summarize_ux(d)['categories']['passthrough']
            self.assertEqual(r['matching_lines'], LIMIT+3)
            self.assertEqual(len(r['sites']), LIMIT)
            self.assertTrue(r['truncated'])
