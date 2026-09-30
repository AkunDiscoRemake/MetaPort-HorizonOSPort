# SPDX-License-Identifier: GPL-3.0-only
import unittest
from guest.probe import signal_trace_parameters,signal_observations,classify


class SignalTraceTests(unittest.TestCase):
    def test_opt_in_metadata_only_no_security_bypass(self):
        self.assertEqual(signal_trace_parameters(False),'')
        self.assertEqual(signal_trace_parameters(True),
                         'trace_event=signal:signal_generate,sched:sched_process_exit tp_printk ignore_loglevel')
        with self.assertRaises(ValueError):signal_trace_parameters('yes')

    def test_signal_generation_is_not_registration_mount_or_root_cause(self):
        text=('[90.5] signal_generate: sig=6 errno=0 code=-6 comm=keystore2 pid=252 grp=0 res=0\n'
              '[91.0] sched_process_exit: comm=keystore2 pid=252 prio=120\n')
        observation=signal_observations(text)
        self.assertTrue(observation['trace_observed'])
        self.assertTrue(observation['security_trace_observed'])
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

    def test_early_generic_trace_does_not_establish_security_coverage(self):
        observation=signal_observations(
            'sched_process_exit: comm=cryptomgr_test pid=32 prio=120\n'
            "init: ... started service 'keystore2' has pid 251\n")
        self.assertTrue(observation['trace_observed'])
        self.assertFalse(observation['security_trace_observed'])
        self.assertEqual(observation['security_event_count'],0)

    def test_bounded_event_report(self):
        text='\n'.join(f'signal_generate: sig=17 errno=0 code=1 comm=init pid=1 grp=1 res=0' for _ in range(400))
        observation=signal_observations(text)
        self.assertEqual(observation['event_count'],400)
        self.assertEqual(len(observation['events']),200)
        self.assertTrue(observation['events_truncated'])

    def test_late_security_signals_survive_unrelated_event_flood(self):
        text="init: ... started service 'vendor.keymint-qti' has pid 233\n"
        text+='signal_generate: sig=17 errno=0 code=1 comm=init pid=1 grp=1 res=0\n'*300
        text+='signal_generate: sig=6 errno=0 code=-6 comm=keystore2 pid=252 grp=0 res=0\n'
        text+='signal_generate: sig=11 errno=0 code=1 comm=android.hardwar pid=233 grp=0 res=0\n'
        observation=signal_observations(text)
        self.assertEqual(len(observation['events']),200)
        self.assertEqual([s['target_pid'] for s in observation['security_generated_signals']],[252,233])
        self.assertEqual(observation['service_pid_candidates'][233],'vendor.keymint-qti')
        self.assertEqual(observation['security_event_count'],2)
