# SPDX-License-Identifier: GPL-3.0-only
"""Script-level fixtures only: no emulator, firmware, or Gradle execution claimed."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]

class RuntimeScript(unittest.TestCase):
    def run_fixture(self, gradle_exit):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);sdk=root/'SDK with spaces';binpath=root/'bin'
            (sdk/'platform-tools').mkdir(parents=True);binpath.mkdir()
            for path,body in (
                (sdk/'platform-tools/adb', 'echo "adb:$*" >> "$CALLS"\n'),
                (binpath/'timeout', 'shift\nexec "$@"\n'),
                (binpath/'gradle', 'echo "gradle:$*" >> "$CALLS"\nexit "$FAKE_GRADLE_EXIT"\n')):
                path.write_text('#!/bin/sh\n'+body);path.chmod(0o755)
            env=dict(os.environ,ANDROID_HOME=str(sdk),PATH=str(binpath)+':'+os.environ['PATH'],
                     CALLS=str(root/'calls'),FAKE_GRADLE_EXIT=str(gradle_exit))
            result=subprocess.run(['bash',str(ROOT/'tools/run_android_runtime.sh')],cwd=root,
                                  env=env,capture_output=True,timeout=10)
            return result.returncode,(root/'calls').read_text()

    def test_absolute_sdk_adb_and_cleanup(self):
        code,calls=self.run_fixture(0)
        self.assertEqual(code,0)
        self.assertIn('adb:shell setprop debug.checkjni 1',calls)
        self.assertIn('adb:logcat -c',calls)
        self.assertIn('adb:logcat -d',calls)
        self.assertIn(':adapters:connectedDebugAndroidTest',calls)

    def test_gradle_failure_preserved_with_cleanup(self):
        code,calls=self.run_fixture(9)
        self.assertEqual(code,9)
        self.assertIn('adb:logcat -d',calls)
