import unittest
from guest.probe import classify


class ProbeTests(unittest.TestCase):
    def test_kernel_is_not_android(self):
        r=classify('[0.0] Booting Linux on physical CPU 0\n[0.1] Linux version 5.10.240')
        self.assertTrue(r['kernel_console_observed']);self.assertFalse(r['android_boot_completed'])
        self.assertFalse(r['original_init_marker_observed'])

    def test_first_stage_is_not_full_boot(self):
        r=classify('[1.0] init: init first stage started!\nKernel panic - not syncing')
        self.assertTrue(r['original_init_marker_observed']);self.assertTrue(r['kernel_panic_observed'])
        self.assertFalse(r['android_boot_completed'])

    def test_empty_output_is_not_success(self):
        self.assertFalse(classify('')['kernel_console_observed'])

    def test_exec_attempt_is_not_first_stage_start(self):
        r=classify('Run /init as init process\nKernel panic - not syncing: Attempted to kill init! exitcode=0x00000004')
        self.assertTrue(r['original_init_exec_attempt_observed'])
        self.assertTrue(r['init_sigill_observed'])
        self.assertFalse(r['original_init_marker_observed'])

    def test_recovery_is_distinguished(self):
        r=classify('init: init first stage started!\ninit: First stage mount skipped (recovery mode)')
        self.assertTrue(r['original_init_marker_observed'])
        self.assertTrue(r['recovery_mount_skip_observed'])
        self.assertFalse(r['android_boot_completed'])

    def test_second_stage_and_mount_evidence_is_not_complete_boot(self):
        r=classify("init: init second stage started!\ninit: Created logical partition system_a on device /dev/block/dm-0\ninit: __mount(source=/dev/block/dm-7,target=/system,type=ext4)=0: Success")
        self.assertTrue(r['second_stage_init_observed'])
        self.assertEqual(r['logical_partitions_created'],['system_a'])
        self.assertEqual(len(r['boot_events']),3)
        self.assertFalse(r['android_boot_completed'])

    def test_whole_disk_denial_is_not_misc_and_hidl_is_not_full_boot(self):
        text=('avc: denied { read write } name="vda" scontext=u:r:hal_bootctl_default:s0 tcontext=u:object_r:vd_device:s0\n'
              'update_verifier: Using HIDL version 1.2 of IBootControl\n'
              "init: starting service 'zygote'...\ninit: Service 'zygote' (pid 1) received signal 6")
        r=classify(text)
        self.assertFalse(r['bootcontrol_misc_label_denial_observed'])
        self.assertTrue(r['bootcontrol_disk_label_denial_observed'])
        self.assertTrue(r['bootcontrol_hidl12_client_observed'])
        self.assertTrue(r['zygote_start_attempt_observed'])
        self.assertTrue(r['zygote_termination_observed'])
        self.assertFalse(r['android_boot_completed'])
