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

    def run_fixture(self,abi='x86_64,arm64-v8a',install='Failure [INSTALL_FAILED_MISSING_SHARED_LIBRARY]',code=1,uid_output='',crash_text='',pid_text=''):
        with tempfile.TemporaryDirectory() as d:
            apk=Path(d)/'test.apk';apk.write_bytes(b'fixture only')
            policy=Path(d)/'policy.json';policy.write_text(json.dumps({'apk_sha256':hashlib.sha256(apk.read_bytes()).hexdigest()}))
            calls=[]
            def fake(adb,args,timeout):
                calls.append(args)
                text=abi if 'ro.product.cpu.abilist' in args else install if args[0]=='install' else uid_output if 'packages' in args else ''
                if 'pidof' in args:text=pid_text
                if args[0]=='logcat' and 'crash' in args and '-d' in args:text=crash_text
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
            main_logs=[c for c in calls if c[0]=='logcat' and 'main' in c]
            loader=[c for c in main_logs if any(a.startswith('--regex=') for a in c)]
            self.assertEqual(len(loader),2)
            for c in loader:self.assertIn('1200',c);self.assertIn('-d',c)
            self.assertIn('loader_log_after_install',report);self.assertIn('loader_log_after_start',report)
            logs=[c for c in main_logs if c not in loader]
            if expected:
                self.assertEqual(len(logs),1)
                self.assertIn('--uid=10209',logs[0]);self.assertIn('400',logs[0])
            else:
                self.assertEqual(logs,[]);self.assertNotIn('application_log',report)

    def test_replacement_pid_does_not_hide_original_app_crash(self):
        for crash in ('pid: 2687, tid: 2687 >>> com.oculus.vrshell <<<',
                      'Process: com.oculus.vrshell, PID: 2687'):
            r,_=self.run_fixture(install='Success',code=0,crash_text=crash,pid_text='3446\n')
            self.assertEqual(r['result'],'APPLICATION_CRASH_RECORDED')
            self.assertTrue(r['application_crash_recorded'])
            self.assertFalse(r['port_ready'])
        r,_=self.run_fixture(install='Success',code=0,crash_text='>>> unrelated.app <<<')
        self.assertFalse(r['application_crash_recorded'])
