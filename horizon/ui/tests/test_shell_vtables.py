# SPDX-License-Identifier: GPL-3.0-only
import unittest
from horizon.ui.inspect_shell_vtables import windows
from handtracking.ai.tests.test_elf_pointer_evidence import fixture

class VtableWindows(unittest.TestCase):
    def inspect(self, relocations=None, address=0x1108):
        return windows(fixture(), relocations or {},
                       [{'address_point_elf':address,'constructor_elf':0x2000}],slots=2)

    def test_raw_is_only_candidate(self):
        r=self.inspect();row=r['windows'][0]['slots'][2]
        self.assertEqual(row['candidate_target_elf'],0x2000)
        self.assertEqual(row['kind'],'RAW64_CANDIDATE')
        self.assertTrue(row['points_into_file_backed_executable_segment'])
        self.assertFalse(r['private_abi_validated']);self.assertFalse(r['vtable_extent_validated'])

    def test_relocation_overrides_file(self):
        row=self.inspect({0x1108:(0x1020,'R_AARCH64_RELATIVE')})['windows'][0]['slots'][2]
        self.assertEqual(row['raw_u64'],0x2000)
        self.assertEqual(row['candidate_target_elf'],0x1020)
        self.assertFalse(row['points_into_file_backed_executable_segment'])

    def test_bounds_and_unmapped(self):
        with self.assertRaises(ValueError):self.inspect(address=0x1101)
        with self.assertRaises(ValueError):windows(fixture(),{},slots=65)
        self.assertEqual(self.inspect(address=0x3000)['windows'][0]['slots'][0]['kind'],'UNMAPPED_OR_BSS')
