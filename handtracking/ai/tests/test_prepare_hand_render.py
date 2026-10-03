# SPDX-License-Identifier: GPL-3.0-only
import struct
import unittest
from handtracking.ai.prepare_hand_render import file_offset_va


def elf():
    blob=bytearray(256);blob[:6]=b'\x7fELF\x02\x01'
    struct.pack_into('<H',blob,18,183);struct.pack_into('<Q',blob,32,64)
    struct.pack_into('<HH',blob,54,56,1)
    struct.pack_into('<IIQQQQQQ',blob,64,1,4,128,0x4000,0,64,80,4096)
    return blob


class RenderAddressTests(unittest.TestCase):
    def test_elf_va_not_file_offset_or_ghidra_address(self):
        self.assertEqual(file_offset_va(elf(),128),0x4000)
        self.assertEqual(file_offset_va(elf(),191),0x403f)
        for offset in (127,192,256,-1,True):
            with self.assertRaises(ValueError):file_offset_va(elf(),offset)

    def test_bad_headers_ranges_and_overlapping_loads_rejected(self):
        for position,fmt,value in ((18,'H',62),(54,'H',48),(56,'H',257),(32,'Q',240),(96,'Q',300)):
            blob=elf();struct.pack_into('<'+fmt,blob,position,value)
            with self.assertRaises(ValueError):file_offset_va(blob,128)
        blob=elf();struct.pack_into('<H',blob,56,2);blob[120:176]=blob[64:120]
        with self.assertRaises(ValueError):file_offset_va(blob,180)
