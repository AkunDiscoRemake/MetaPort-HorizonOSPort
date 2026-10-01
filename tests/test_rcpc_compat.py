# SPDX-License-Identifier: GPL-3.0-only
import hashlib
import struct
import unittest
from horizon.ui.rcpc_compat import lower_verified,BEFORE,AFTER
from tests import test_shell_crash_windows as fixture

class RcpcAdaptation(unittest.TestCase):
    def test_exact_site_only_and_fail_closed(self):
        original=bytearray(fixture.CrashInstructions().image());struct.pack_into('<I',original,256,BEFORE)
        original=bytes(original);sha=hashlib.sha256(original).hexdigest()
        adapted,r=lower_verified(original,sha,4096)
        self.assertEqual(struct.unpack_from('<I',adapted,256)[0],AFTER)
        self.assertEqual(original[:256],adapted[:256]);self.assertEqual(original[260:],adapted[260:])
        self.assertEqual(r['source_sha256'],sha);self.assertFalse(r['complete_cpu_compatibility'])
        for data,digest,pc in ((original,'wrong',4096),(adapted,hashlib.sha256(adapted).hexdigest(),4096),(original,sha,0)):
            with self.assertRaises(ValueError):lower_verified(data,digest,pc)
