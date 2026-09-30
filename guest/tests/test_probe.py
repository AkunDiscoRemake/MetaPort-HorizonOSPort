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
