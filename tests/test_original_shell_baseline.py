# SPDX-License-Identifier: GPL-3.0-only
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from tools.probe_original_shell import inspect,offline_guard

class OriginalBaseline(unittest.TestCase):
    def test_network_guard_rejects_external_interfaces(self):
        for items in ([],[{'ifname':'lo'},{'ifname':'eth0'}]):
            with patch('tools.probe_original_shell.subprocess.check_output',return_value=json.dumps(items)):
                with self.assertRaises(RuntimeError):offline_guard()
        with patch('tools.probe_original_shell.subprocess.check_output',return_value='[{"ifname":"lo"}]'):
            offline_guard()

    def run_fixture(self,abi='x86_64,arm64-v8a',install='Failure [INSTALL_FAILED_MISSING_SHARED_LIBRARY]',code=1):
        with tempfile.TemporaryDirectory() as d:
            apk=Path(d)/'test.apk';apk.write_bytes(b'fixture only')
            policy=Path(d)/'policy.json';policy.write_text(json.dumps({'apk_sha256':hashlib.sha256(apk.read_bytes()).hexdigest()}))
            calls=[]
            def fake(adb,args,timeout):
                calls.append(args)
                text=abi if 'ro.product.cpu.abilist' in args else install if args[0]=='install' else ''
                return {'exit_code':code if args[0]=='install' else 0,'text':text,'truncated':False}
            with patch('tools.probe_original_shell.POLICY',policy), \
                 patch('tools.probe_original_shell.offline_guard'), \
                 patch('tools.probe_original_shell.adb_command',side_effect=fake):
                return inspect(apk,'adb',observe_seconds=0),calls

    def test_unsupported_abi_never_installs(self):
        report,calls=self.run_fixture(abi='x86_64')
        self.assertFalse(report['installation_attempted'])
        self.assertFalse(any(c[0]=='install' for c in calls))

    def test_install_failure_is_not_a_port(self):
        report,calls=self.run_fixture()
        self.assertEqual(report['result'],'INSTALL_REJECTED')
        self.assertFalse(report['port_ready'])
        self.assertFalse(report['activity_start_attempted'])

    def test_start_and_cleanup_do_not_claim_ui_success(self):
        report,calls=self.run_fixture(install='Success',code=0)
        self.assertTrue(report['installation_succeeded'])
        self.assertTrue(report['activity_start_attempted'])
        self.assertFalse(report['original_ui_rendering_validated'])
        self.assertEqual(calls[-1],['shell','am','force-stop','com.oculus.vrshell'])

    def test_bad_hash_never_runs_adb(self):
        with tempfile.TemporaryDirectory() as d,patch('tools.probe_original_shell.adb_command') as call:
            apk=Path(d)/'bad.apk';apk.write_bytes(b'bad')
            with self.assertRaises(ValueError):inspect(apk,'adb')
            call.assert_not_called()
