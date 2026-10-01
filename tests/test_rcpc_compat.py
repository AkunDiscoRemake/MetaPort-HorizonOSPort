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
        adapted,r=lower_verified(original,sha,((4096,BEFORE,AFTER),))
        self.assertEqual(struct.unpack_from('<I',adapted,256)[0],AFTER)
        self.assertEqual(original[:256],adapted[:256]);self.assertEqual(original[260:],adapted[260:])
        self.assertEqual(r['source_sha256'],sha);self.assertFalse(r['complete_cpu_compatibility'])
        for data,digest,pc in ((original,'wrong',4096),(adapted,hashlib.sha256(adapted).hexdigest(),4096),(original,sha,0)):
            with self.assertRaises(ValueError):lower_verified(data,digest,((pc,BEFORE,AFTER),))

    def test_register_changes_and_duplicate_sites_are_rejected(self):
        original=bytearray(fixture.CrashInstructions().image());struct.pack_into('<I',original,256,BEFORE)
        original=bytes(original);sha=hashlib.sha256(original).hexdigest()
        for sites in (((4096,BEFORE,AFTER^1),),((4096,BEFORE,AFTER),)*2):
            with self.assertRaises(ValueError):lower_verified(original,sha,sites)

    def test_wide_load_retains_width_and_registers(self):
        original=bytearray(fixture.CrashInstructions().image())
        before=0xf8bfc2a8;after=0xc8dffea8
        struct.pack_into('<I',original,256,before);original=bytes(original)
        sha=hashlib.sha256(original).hexdigest()
        result,_=lower_verified(original,sha,((4096,before,after),))
        self.assertEqual(struct.unpack_from('<I',result,256)[0],after)
        self.assertEqual(result[260:],original[260:])
        with self.assertRaises(ValueError):lower_verified(original,sha,((4096,before,0x08dffea8),))

    def test_inventory_is_explicit_and_every_encoding_preserves_width(self):
        from horizon.ui.rcpc_compat import SITES
        self.assertEqual(len(SITES),206)
        self.assertEqual(len(set(pc for pc,_,_ in SITES)),206)
        for pc,before,after in SITES:
            self.assertEqual(pc%4,0)
            self.assertEqual(before&1023,after&1023)
            self.assertEqual(before>>30,after>>30)
            self.assertIn((before&0xfffffc00,after&0xfffffc00),
                          ((0x38bfc000,0x08dffc00),(0xf8bfc000,0xc8dffc00)))

    def test_word_acquire_and_library_identity_are_preserved(self):
        original=bytearray(fixture.CrashInstructions().image());before=0xb8bfc008;after=0x88dffc08
        struct.pack_into('<I',original,256,before);original=bytes(original)
        sha=hashlib.sha256(original).hexdigest()
        result,evidence=lower_verified(original,sha,((4096,before,after),),library='libutils.so')
        self.assertEqual(evidence['library'],'libutils.so')
        self.assertEqual(struct.unpack_from('<I',result,256)[0],after)
        self.assertEqual(result[:256]+result[260:],original[:256]+original[260:])
        with self.assertRaises(ValueError):lower_verified(original,sha,((4096,before,0xc8dffc08),))
