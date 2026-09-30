import unittest
from guest.diagnostics import configuration,IMPORTS


class DiagnosticConfigTests(unittest.TestCase):
    def test_preserves_boot_imports_and_excludes_kernel_feedback(self):
        text=configuration()
        self.assertEqual([l[7:] for l in text.splitlines() if l.startswith('import ')],list(IMPORTS))
        self.assertIn('/system/bin/logcat -b main -b system -b crash',text)
        self.assertNotIn('-b all',text)
        self.assertNotIn('-b kernel',text)
        self.assertNotIn('setenforce',text)
        self.assertNotIn('seclabel',text)
        self.assertIn('stdio_to_kmsg',text)

    def test_actual_denials_are_not_success(self):
        from guest.probe import classify
        text=("init: Command 'mount none /metadata/vendor_file_contexts.metaport /vendor/etc/selinux/vendor_file_contexts bind' took 2ms and failed: mount() failed: Permission denied\n"
              "avc: denied { getattr } scontext=u:r:hal_bootctl_default:s0 tcontext=u:object_r:vd_device:s0 tclass=blk_file permissive=0\n"
              "avc: denied { getattr } scontext=u:r:init:s0 tcontext=u:object_r:logcat_exec:s0 permissive=0")
        r=classify(text)
        self.assertTrue(r['label_overlay_mount_failed'])
        self.assertTrue(r['bootcontrol_misc_label_denial_observed'])
        self.assertTrue(r['diagnostic_logger_denied_observed'])
        self.assertFalse(r['android_boot_completed'])
