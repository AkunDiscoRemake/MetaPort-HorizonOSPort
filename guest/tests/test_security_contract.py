# SPDX-License-Identifier: GPL-3.0-only
import unittest
from guest.security_contract import parse_init,select
from guest.probe import security_observations,classify


class SecurityContractTests(unittest.TestCase):
    def test_service_actions_and_imports_are_evidence_not_executed(self):
        text=('import /vendor/etc/init/${ro.hardware}.rc\n'
              'service keystore2 /system/bin/keystore2 /data/misc/keystore\n'
              '    class early_hal\n    user keystore\n    disabled\n'
              '    interface aidl android.system.keystore2.IKeystoreService/default\n'
              'on post-fs\n    start keystore2\n'
              'on property:example=1 && property:other=2\n    exec -- /bin/example "a b"\n')
        result=parse_init(text)
        self.assertEqual(result['services'][0]['name'],'keystore2')
        self.assertIn('disabled',result['services'][0]['options'])
        self.assertEqual(result['actions'][0]['commands'],['start keystore2'])
        self.assertEqual(result['actions'][1]['trigger'],'property:example=1 && property:other=2')
        self.assertEqual(result['imports'][0]['expression'],'/vendor/etc/init/${ro.hardware}.rc')
        self.assertFalse(result['commands_executed'])
        self.assertFalse(result['complete_init_grammar'])

    def test_continuations_keep_literal_arguments(self):
        result=parse_init('service test /bin/test \\\n  --flag="x y"\n    class core\n')
        self.assertIn('--flag="x y"',result['services'][0]['command_line'])
        self.assertEqual(result['services'][0]['line'],1)
        for raw in ('service incomplete\n','service x /bin/x \\', 'x'*8193, 'x\n'*8193):
            with self.assertRaises(ValueError):parse_init(raw)

    def test_inventory_missing_and_duplicate_paths_fail(self):
        row={'path':'/bin/service','kind':'file'}
        self.assertEqual(select([row],{'/bin/service'}),{'/bin/service':row})
        with self.assertRaises(ValueError):select([],{row['path']})
        with self.assertRaises(ValueError):select([row,row],{row['path']})

    def test_start_and_encrypt_request_are_not_mount_or_registration(self):
        text=("[1] init: starting service 'keystore2'...\n"
              "[2] init: starting service 'vendor.keymint-qti'...\n"
              '[3] init: Calling: /system/bin/vdc cryptfs encryptFstab /dev/block/by-name/userdata /data true ext4\n'
              '[4] ServiceManagerCppClient: Waited one second for android.system.keystore2.IKeystoreService/default\n')
        result=classify(text)
        observation=result['security_startup']
        self.assertTrue(observation['keystore_start_attempt_observed'])
        self.assertTrue(observation['keymint_start_attempt_observed'])
        self.assertTrue(observation['keystore_service_wait_observed'])
        self.assertTrue(observation['userdata_encryption_request_observed'])
        self.assertEqual(observation['userdata_mounted'],'NOT_ESTABLISHED')
        self.assertEqual(observation['keystore_registered'],'NOT_ESTABLISHED')
        self.assertFalse(result['android_boot_completed'])

    def test_retry_loop_does_not_hide_early_failures_or_fill_report(self):
        text="[0] init: Service 'keystore2' exited with status 1\n"
        text+='\n'.join(f'[{i}] keystore2: repeated wait' for i in range(1000))
        observation=security_observations(text)
        self.assertIn('exited with status',observation['events'][0])
        self.assertEqual(len(observation['events']),4)
        self.assertEqual(observation['matching_line_count'],1001)
        self.assertEqual(observation['omitted_line_count'],997)
        many='\n'.join(f'keystore2: different diagnostic {i}' for i in range(300))
        self.assertEqual(len(security_observations(many)['events']),160)
        self.assertEqual(security_observations('')['matching_line_count'],0)
