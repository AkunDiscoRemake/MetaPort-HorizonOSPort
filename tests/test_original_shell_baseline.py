# SPDX-License-Identifier: GPL-3.0-only
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from tools.probe_original_shell import inspect,offline_guard,package_uid

class OriginalBaseline(unittest.TestCase):
    def test_network_guard_rejects_external_interfaces(self):
        for items in ([],[{'ifname':'lo'},{'ifname':'eth0'}]):
            with patch('tools.probe_original_shell.subprocess.check_output',return_value=json.dumps(items)):
                with self.assertRaises(RuntimeError):offline_guard()
        with patch('tools.probe_original_shell.subprocess.check_output',return_value='[{"ifname":"lo"}]'):
            offline_guard()

    def run_fixture(self,abi='x86_64,arm64-v8a',install='Failure [INSTALL_FAILED_MISSING_SHARED_LIBRARY]',code=1,uid_output=''):
        with tempfile.TemporaryDirectory() as d:
            apk=Path(d)/'test.apk';apk.write_bytes(b'fixture only')
            policy=Path(d)/'policy.json';policy.write_text(json.dumps({'apk_sha256':hashlib.sha256(apk.read_bytes()).hexdigest()}))
            calls=[]
            def fake(adb,args,timeout):
                calls.append(args)
                text=abi if 'ro.product.cpu.abilist' in args else install if args[0]=='install' else uid_output if 'packages' in args else ''
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

    def test_uid_filter_requires_unique_exact_app(self):
        self.assertEqual(package_uid('package:com.oculus.vrshell uid:10209\n'),10209)
        for text in ('package:com.oculus.vrshell.other uid:10209',
                     'package:com.oculus.vrshell uid:0',
                     'package:com.oculus.vrshell uid:10209\n'*2,'Error: denied'):
            self.assertIsNone(package_uid(text))

    def test_main_log_is_bounded_and_filtered_or_omitted(self):
        for identity,expected in (('package:com.oculus.vrshell uid:10209',10209),('unknown',None)):
            report,calls=self.run_fixture(install='Success',code=0,uid_output=identity)
            self.assertEqual(report['application_uid'],expected)
            logs=[c for c in calls if c[0]=='logcat' and 'main' in c]
            if expected:
                self.assertEqual(len(logs),1)
                self.assertIn('--uid=10209',logs[0]);self.assertIn('400',logs[0])
            else:
                self.assertEqual(logs,[]);self.assertNotIn('application_log',report)
