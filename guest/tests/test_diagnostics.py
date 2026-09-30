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
