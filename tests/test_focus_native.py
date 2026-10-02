# SPDX-License-Identifier: GPL-3.0-only
import hashlib
import struct
import unittest
from horizon.ui.prepare_focus_native import verify_elf

class FocusNativeTests(unittest.TestCase):
    def test_identity_and_architecture_are_both_required(self):
        data=bytearray(64);data[:6]=b'\x7fELF\x02\x01';struct.pack_into('<HH',data,16,3,183)
        data=bytes(data);sha=hashlib.sha256(data).hexdigest()
        verify_elf(data,len(data),sha)
        with self.assertRaises(ValueError):verify_elf(data,len(data)+1,sha)
        with self.assertRaises(ValueError):verify_elf(data,len(data),'0'*64)
        wrong=bytearray(data);struct.pack_into('<H',wrong,18,62);wrong=bytes(wrong)
        with self.assertRaises(ValueError):verify_elf(wrong,len(wrong),hashlib.sha256(wrong).hexdigest())
