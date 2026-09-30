# SPDX-License-Identifier: GPL-3.0-only
import unittest
from guest.probe import signal_trace_parameters,signal_observations,classify


class SignalTraceTests(unittest.TestCase):
    def test_opt_in_metadata_only_no_security_bypass(self):
        self.assertEqual(signal_trace_parameters(False),'')
        self.assertEqual(signal_trace_parameters(True),
                         'trace_event=signal:signal_generate,sched:sched_process_exit tp_printk')
        with self.assertRaises(ValueError):signal_trace_parameters('yes')

    def test_signal_generation_is_not_registration_mount_or_root_cause(self):
        text=('[90.5] signal_generate: sig=6 errno=0 code=-6 comm=keystore2 pid=252 grp=0 res=0\n'
              '[91.0] sched_process_exit: comm=keystore2 pid=252 prio=120\n')
        observation=signal_observations(text)
        self.assertTrue(observation['trace_observed'])
        self.assertEqual(observation['generated_signals'][0]['target_pid'],252)
        self.assertEqual(observation['generated_signals'][0]['signal'],6)
        self.assertEqual(observation['generated_signals'][0]['si_code'],-6)
        self.assertEqual(observation['process_exits'][0]['pid'],252)
        self.assertEqual(observation['fatal_cause'],'NOT_ESTABLISHED_BY_SIGNAL_GENERATION')
        self.assertFalse(classify(text)['android_boot_completed'])

    def test_command_line_and_missing_events_do_not_prove_enabled_trace(self):
        observation=signal_observations('Kernel command line: '+signal_trace_parameters(True))
        self.assertFalse(observation['trace_observed'])
        self.assertEqual(observation['generated_signals'],[])

    def test_bounded_event_report(self):
        text='\n'.join(f'signal_generate: sig=17 errno=0 code=1 comm=init pid=1 grp=1 res=0' for _ in range(400))
        observation=signal_observations(text)
        self.assertEqual(observation['event_count'],400)
        self.assertEqual(len(observation['events']),200)
        self.assertTrue(observation['events_truncated'])
