# SPDX-License-Identifier: GPL-3.0-only
import struct
import unittest
from horizon.tracking.inspect_hand_dependencies import elf_identity, text_evidence, disassembly_summary, executable_section_view


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

    def test_context_keeps_setting_next_to_comment(self):
        r=text_evidence(b'# hand scheduler\nvalue=4\nother=2\n')
        self.assertEqual(r['matched_lines'],1)
        self.assertEqual(r['lines'][1]['excerpt'],'value=4')
        self.assertFalse(r['lines'][1]['keyword_match'])

    def test_disassembly_is_evidence_not_activation(self):
        r=disassembly_summary('00001000 <conv_kernel>:\n 1000: v0.b = vadd(v1.b,v2.b)\n 1004: jumpr r31\n')
        self.assertEqual(r['instruction_lines'],2)
        self.assertEqual(r['vector_syntax_lines'],1)
        self.assertEqual(r['function_labels'],['conv_kernel'])
        self.assertFalse(r['hand_call_chain_validated'])

    def test_vector_samples_are_bounded(self):
        r=disassembly_summary(' 1000: v0.b = vadd(v1.b,v2.b)\n'*100)
        self.assertEqual(r['vector_syntax_lines'],100)
        self.assertEqual(len(r['vector_samples']),64)
        self.assertTrue(r['vector_samples_truncated'])

    def test_sectionless_hexagon_view_preserves_payload(self):
        data=bytearray(100);data[:7]=b'\x7fELF\x01\x01\x01'
        struct.pack_into('<H',data,18,164)
        struct.pack_into('<I',data,28,52)
        struct.pack_into('<HH',data,42,32,1)
        struct.pack_into('<8I',data,52,1,84,0x1000,0x1000,16,16,5,4)
        data[84:]=bytes(range(16))
        view=executable_section_view(data)
        self.assertEqual(view[84:100],data[84:100])
        shoff=struct.unpack_from('<I',view,32)[0]
        self.assertGreaterEqual(shoff,100)
        self.assertEqual(struct.unpack_from('<HHH',view,46),(40,3,2))
        entry=struct.unpack_from('<10I',view,shoff+40)
        self.assertEqual(entry[1:6],(1,6,0x1000,84,16))
        struct.pack_into('<I',data,52+16,1000)
        with self.assertRaises(ValueError): executable_section_view(data)

    def test_section_view_rejects_wrong_machine(self):
        data=bytearray(64);data[:6]=b'\x7fELF\x02\x01';struct.pack_into('<H',data,18,183)
        with self.assertRaises(ValueError): executable_section_view(data)
