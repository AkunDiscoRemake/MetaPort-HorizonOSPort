# SPDX-License-Identifier: GPL-3.0-only
import io
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch
from tools.boot_android_emulator import configure, capture, wait_for_boot

class EmulatorSupervisor(unittest.TestCase):
    def test_config_replaces_duplicates_and_correct_heap_key(self):
        result=configure('hw.ramSize=100\nhw.ramSize=200\nvm.heapSize=16\ncustom=value\n')
        self.assertEqual(result.count('hw.ramSize='),1)
        self.assertIn('vm.heapSize=512\n',result)
        self.assertIn('custom=value\n',result)

    def test_capture_drains_but_bounds_storage(self):
        stream=io.BytesIO(b'x'*20000)
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'log';capture(stream,p,limit=100)
            self.assertEqual(p.read_bytes(),b'x'*100)
            self.assertEqual(stream.tell(),20000)

    def test_early_exit_not_waited_out(self):
        with patch('tools.boot_android_emulator.subprocess.run') as call:
            with self.assertRaisesRegex(RuntimeError,'exit 7'):
                wait_for_boot(Mock(poll=lambda:7),'adb',10)
            call.assert_not_called()

    def test_boot_requires_success_and_exact_property(self):
        results=[SimpleNamespace(returncode=1,stdout=b'1'),
                 SimpleNamespace(returncode=0,stdout=b'0'),
                 SimpleNamespace(returncode=0,stdout=b'1\n')]
        with patch('tools.boot_android_emulator.subprocess.run',side_effect=results) as call, \
             patch('tools.boot_android_emulator.time.sleep'):
            wait_for_boot(Mock(poll=lambda:None),'adb',10)
        self.assertEqual(call.call_count,3)

    def test_deadline_failure(self):
        with patch('tools.boot_android_emulator.time.monotonic',side_effect=[0,2]):
            with self.assertRaises(TimeoutError):
                wait_for_boot(Mock(poll=lambda:None),'adb',1)
