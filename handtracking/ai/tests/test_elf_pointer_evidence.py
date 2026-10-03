# SPDX-License-Identifier: GPL-3.0-only
import struct
import unittest
from handtracking.ai.elf_pointer_evidence import PointerIndex,parse_relocations,load_segments


def fixture():
    data=bytearray(1024);data[:6]=b'\x7fELF\x02\x01';struct.pack_into('<H',data,18,183)
    struct.pack_into('<Q',data,32,64);struct.pack_into('<HH',data,54,56,2)
    struct.pack_into('<II6Q',data,64,1,4,256,0x1000,0,512,512,8)
    struct.pack_into('<II6Q',data,120,1,5,768,0x2000,0,256,256,4)
    # String pointer in typeinfo at +8, typeinfo pointer in a possible vtable.
    struct.pack_into('<Q',data,256+0x88,0x1020)
    struct.pack_into('<Q',data,256+0x100,0x1080)
    struct.pack_into('<Q',data,256+0x108,0x2000)
    return data


class ElfPointers(unittest.TestCase):
    def trace(self,index):
        return index.trace([{'text':'DPEPredictorV2','address':0x1020}])['targets'][0]

    def test_raw_chain_is_only_candidate(self):
        r=self.trace(PointerIndex(fixture(),{}));p=r['paths'][0]
        self.assertEqual(r['name_pointer_count'],1)
        self.assertEqual(p['executable_pointer_candidates'][0]['target_elf'],0x2000)
        self.assertEqual(p['name_pointer_kind'],'RAW64_CANDIDATE')

    def test_relocation_overrides_zero_file_word(self):
        data=fixture();struct.pack_into('<Q',data,256+0x88,0)
        rels,stats=parse_relocations('00001088 000000000403 R_AARCH64_RELATIVE 1020\n')
        p=self.trace(PointerIndex(data,rels))['paths'][0]
        self.assertEqual(p['name_pointer_kind'],'R_AARCH64_RELATIVE')
        self.assertFalse(stats['complete_relocation_coverage'])

    def test_local_symbol_only_and_duplicate_rejected(self):
        r,s=parse_relocations('1100 000100000101 R_AARCH64_ABS64 00001080 _ZTIfoo + 0\n1108 000200000101 R_AARCH64_ABS64 00000000 external + 0\n')
        self.assertEqual(r,{0x1100:(0x1080,'R_AARCH64_ABS64')})
        with self.assertRaises(ValueError):parse_relocations(('1088 403 R_AARCH64_RELATIVE 1020\n')*2)

    def test_bounds_and_overlap(self):
        with self.assertRaises(ValueError):load_segments(b'bad')
        data=fixture();struct.pack_into('<Q',data,120+16,0x1100)
        with self.assertRaises(ValueError):load_segments(data)

    def test_non_executable_and_unaligned_values_not_code(self):
        for pointer in (0x1020,0x2001):
            data=fixture();struct.pack_into('<Q',data,256+0x108,pointer)
            self.assertEqual(self.trace(PointerIndex(data,{}))['paths'][0]['executable_pointer_candidates'],[])
