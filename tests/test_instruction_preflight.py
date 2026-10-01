# SPDX-License-Identifier: GPL-3.0-only
import unittest
from unittest.mock import patch
from tools.probe_original_shell import run_experiment,PREFLIGHT_REQUIRED

class InstructionPreflight(unittest.TestCase):
    def test_missing_or_failed_case_prevents_original_install(self):
        for absent in PREFLIGHT_REQUIRED:
            cases={name:{'expected_value_observed':True} for name in PREFLIGHT_REQUIRED if name!=absent}
            with patch('tools.probe_arm64_instructions.inspect',return_value={'cases':cases}), \
                 patch('tools.probe_original_shell.inspect') as original:
                r=run_experiment('original.apk','adb',instruction_probe_apk='probe.apk')
            original.assert_not_called()
            self.assertEqual(r['failed_or_missing_preflight_cases'],[absent])
            self.assertFalse(r['installation_attempted']);self.assertFalse(r['port_ready'])

    def test_passing_instruction_cases_do_not_make_original_app_ready(self):
        cases={name:{'expected_value_observed':True} for name in PREFLIGHT_REQUIRED}
        cases['rcpc32']={'expected_value_observed':False}
        order=[]
        def probe(*args):order.append('probe');return {'cases':cases}
        def app(*args,**kwargs):order.append('original');return {'result':'APPLICATION_CRASH_RECORDED','port_ready':False}
        with patch('tools.probe_arm64_instructions.inspect',side_effect=probe), \
             patch('tools.probe_original_shell.inspect',side_effect=app):
            r=run_experiment('original.apk','adb',instruction_probe_apk='probe.apk')
        self.assertEqual(order,['probe','original'])
        self.assertTrue(r['instruction_preflight_passed']);self.assertFalse(r['port_ready'])
