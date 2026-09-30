# SPDX-License-Identifier: GPL-3.0-only
import struct
import unittest
from horizon.tracking.inspect_hand_dependencies import elf_identity, text_evidence


class Dependencies(unittest.TestCase):
    def test_distinguish_host_from_dsp(self):
        for bits,machine,name in ((2,183,'AArch64'),(1,164,'Hexagon')):
            data=bytearray(64);data[:6]=b'\x7fELF'+bytes((bits,1));struct.pack_into('<H',data,18,machine)
            self.assertEqual(elf_identity(data)['architecture'],name)
        with self.assertRaises(ValueError): elf_identity(b'not an ELF')

    def test_big_endian_and_short_elf64(self):
        data=bytearray(64);data[:6]=b'\x7fELF\x02\x02';struct.pack_into('>H',data,18,183)
        self.assertEqual(elf_identity(data)['machine'],183)
        with self.assertRaises(ValueError): elf_identity(data[:52])

    def test_configuration_not_activation(self):
        r=text_evidence(b'other=true\nhand_tracking=false\nthread_count=4\n')
        self.assertEqual(r['matched_lines'],2)
        self.assertFalse(r['runtime_activation_proved'])
        self.assertEqual(text_evidence(b'a\0hand')['status'],'BINARY_OR_NUL_TEXT')

    def test_text_limits_visible(self):
        r=text_evidence((b'hand'+b'x'*1030+b'\n')*300)
        self.assertTrue(r['truncated']); self.assertTrue(r['lines'][0]['line_truncated'])
        self.assertEqual(len(r['lines']),256)
