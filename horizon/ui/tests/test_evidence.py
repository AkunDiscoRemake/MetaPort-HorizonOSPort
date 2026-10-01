import tempfile
from pathlib import Path
import unittest
from horizon.ui.evidence import summarize_ux, LIMIT

class EvidenceTests(unittest.TestCase):
    def test_separate_categories_and_errors(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d)
            (p/'Shell.java').write_text('// JADX ERROR\nPassthrough.start();\nSurfaceControl.x();\nValueAnimator.x();')
            (p/'layout.xml').write_text('<objectAnimator propertyName="alpha" duration="200"/>')
            r = summarize_ux(p)
            self.assertFalse(r['ui_ported'])
            self.assertEqual(r['resource_files_total'], 1)
            for k in ('passthrough', 'composition'):
                self.assertEqual(r['categories'][k]['matching_lines'], 1)
                self.assertTrue(r['categories'][k]['sites'][0]['has_decompiler_errors'])
            self.assertEqual(r['categories']['ux_animation']['matching_lines'], 2)
            self.assertTrue(any(s['path'].endswith('.xml') for s in r['categories']['ux_animation']['sites']))
    def test_counts_continue_after_bounded_sample(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d)/'Shell.java').write_text('passthrough();\n'*(LIMIT+3))
            r=summarize_ux(d)['categories']['passthrough']
            self.assertEqual(r['matching_lines'], LIMIT+3)
            self.assertEqual(len(r['sites']), LIMIT)
            self.assertTrue(r['truncated'])

    def test_command_forwarding_is_not_camera_passthrough(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d)/'Shell.java').write_text('passThroughShellCommand();\nPassThroughHierarchyChangeListener listener;\nsetPassthroughEnabled(true);')
            r=summarize_ux(d)['categories']['passthrough']
            self.assertEqual(r['matching_lines'], 1)
            self.assertEqual(r['sites'][0]['line'], 3)
    def test_resource_ids_do_not_displace_behavior_sites(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d)/'R.java').write_text('int passthrough_id;\n'*(LIMIT+1))
            (Path(d)/'ZBehavior.java').write_text('setPassthroughEnabled(true);')
            r=summarize_ux(d)['categories']['passthrough']
            self.assertEqual(r['sites'][0]['path'], 'ZBehavior.java')
            self.assertEqual(r['matching_lines'], LIMIT+2)
