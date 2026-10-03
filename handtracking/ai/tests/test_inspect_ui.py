from pathlib import Path
import tempfile
import json
from unittest.mock import patch
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

    def test_app_failures_are_persisted_and_do_not_hide_later_apps(self):
        from handtracking.ai.inspect_ui import inspect
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            reconstruction=root/'reconstruction.json'
            reconstruction.write_text(json.dumps({'partitions':{'system_ext':{'sha256':'verified'}}}))
            apps=['/priv-app/VrShell/VrShell.apk','/priv-app/MetaSystemUI/MetaSystemUI.apk']
            with patch('handtracking.ai.inspect_ui.APKS',apps), \
                 patch('handtracking.ai.inspect_ui.digest',return_value='verified'), \
                 patch('handtracking.ai.inspect_ui.dump_entry',side_effect=ValueError('bounded failure')):
                with self.assertRaisesRegex(ValueError,'One or more'):
                    inspect(root,reconstruction,root/'jadx',root/'report')
            report=json.loads((root/'report/ui-decompilation.json').read_text())
            self.assertEqual([a['path'] for a in report['applications']],apps)
            self.assertTrue(all(a['decompiler_status']=='ANALYSIS_FAILED' for a in report['applications']))
            self.assertFalse(report['ui_ported'])

    def test_oversized_generated_class_is_explicit_partial_coverage(self):
        with tempfile.TemporaryDirectory() as root:
            path=Path(root)/'Huge.java'
            with path.open('wb') as f: f.truncate(4*1024*1024+1)
            (Path(root)/'Small.java').write_text('native void onHand();')
            report=summarize_sources(root)
            self.assertFalse(report['source_coverage_complete'])
            self.assertEqual(report['skipped_oversized_sources'][0]['path'],'Huge.java')
            self.assertEqual(report['native_declarations_total'],1)

    def test_complete_bootstrap_preserves_context_and_marks_missing_classes(self):
        with tempfile.TemporaryDirectory() as root:
            path=Path(root)/'sources/com/oculus/vrshell/ShellApplication.java'
            path.parent.mkdir(parents=True)
            source='class ShellApplication { void before() {} native void init(); void after() {} }'
            path.write_text(source)
            rows=summarize_sources(root)['bootstrap']['classes']
            self.assertEqual(rows[0]['source'],source)
            self.assertFalse(rows[0]['compile_ready'])
            self.assertEqual(rows[1]['status'],'NOT_GENERATED_OR_NOT_REGULAR_FILE')
            path.write_text('// JADX ERROR\n'+source)
            self.assertEqual(summarize_sources(root)['bootstrap']['classes'][0]['status'],'RECONSTRUCTED_WITH_ERRORS')
            with path.open('wb') as f:f.truncate(512*1024+1)
            row=summarize_sources(root)['bootstrap']['classes'][0]
            self.assertEqual(row['status'],'OVERSIZED_NOT_EMBEDDED');self.assertNotIn('source',row)

    def test_native_updater_uses_actual_imported_package(self):
        from handtracking.ai.inspect_ui import BOOTSTRAP_PATHS,summarize_bootstrap
        relative='sources/com/oculus/vrshell/privateipc/updater/ShellNativeUpdaterHolder.java'
        self.assertIn(relative,BOOTSTRAP_PATHS)
        self.assertNotIn('sources/com/oculus/vrshell/ShellNativeUpdaterHolder.java',BOOTSTRAP_PATHS)
        with tempfile.TemporaryDirectory() as root:
            path=Path(root)/relative;path.parent.mkdir(parents=True)
            path.write_text('class ShellNativeUpdaterHolder { native long init(); }')
            row=next(r for r in summarize_bootstrap(root)['classes'] if r['path']==relative)
            self.assertIn('source',row);self.assertFalse(row['runtime_validated'])
