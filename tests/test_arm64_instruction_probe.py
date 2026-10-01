# SPDX-License-Identifier: GPL-3.0-only
import unittest
from unittest.mock import patch
from tools.probe_arm64_instructions import inspect

class InstructionProbe(unittest.TestCase):
    def test_control_pass_and_crashing_extension_remain_distinct(self):
        calls=[]
        def fake(adb,args,timeout):
            calls.append(args)
            text=''
            if args[0]=='install':text='Success\n'
            if 'instrument' in args:
                mode=args[args.index('mode')+1]
                text=('INSTRUMENTATION_RESULT: value=7\nINSTRUMENTATION_CODE: -1\n'
                      if mode=='control' else 'INSTRUMENTATION_RESULT: shortMsg=Process crashed.\nINSTRUMENTATION_CODE: 0\n')
            return {'exit_code':0,'text':text,'truncated':False}
        with patch('tools.probe_arm64_instructions.offline_guard') as guard,patch('tools.probe_arm64_instructions.adb_command',side_effect=fake):
            r=inspect('fixture.apk','adb');guard.assert_called_once()
        self.assertTrue(r['cases']['control']['expected_value_observed'])
        self.assertFalse(r['cases']['lse']['expected_value_observed'])
        self.assertFalse(r['cases']['rcpc']['expected_value_observed'])
        self.assertFalse(r['port_ready'])
        self.assertEqual(calls[-1],['uninstall','org.metaport.internal.cpuprobe'])

    def test_failed_install_never_executes(self):
        with patch('tools.probe_arm64_instructions.offline_guard'),patch('tools.probe_arm64_instructions.adb_command',return_value={'exit_code':1,'text':'Failure','truncated':False}) as command:
            r=inspect('fixture.apk','adb')
        command.assert_called_once();self.assertEqual(r['cases'],{})
