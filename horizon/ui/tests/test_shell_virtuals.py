# SPDX-License-Identifier: GPL-3.0-only
import json
from pathlib import Path
import unittest
from horizon.ui.prepare_shell_virtuals import select, POLICY

class VirtualFrontier(unittest.TestCase):
    def fixture(self):
        return {'library_sha256':'abc','private_abi_validated':False,'firmware_executed':False,
                'windows':[{'constructor_elf':4,'address_point_elf':4096,'slots':[
                    {'relative_byte_offset':o,'candidate_target_elf':8192,'kind':'RAW64_CANDIDATE',
                     'points_into_file_backed_executable_segment':True} for o in (-8,0,8,256)]}]}

    def test_filters_header_and_outside_window_deduplicates_targets(self):
        rows=select(self.fixture(),'abc')
        self.assertEqual(len(rows),1)
        self.assertEqual(len(rows[0]['references']),2)
        self.assertFalse(rows[0]['signature_validated'])

    def test_hash_empty_and_alignment_rejected(self):
        with self.assertRaises(ValueError): select(self.fixture(),'wrong')
        r=self.fixture();r['windows']=[]
        with self.assertRaises(ValueError): select(r,'abc')
        r=self.fixture();r['windows'][0]['slots'][1]['candidate_target_elf']=8193
        with self.assertRaises(ValueError): select(r,'abc')

    def test_published_evidence(self):
        path=Path('analysis/builds/52168470052900520/shell-vtable-windows.json')
        if not path.exists():self.skipTest('Original evidence not shipped in source-only ZIP')
        rows=select(json.loads(path.read_text()),json.loads(POLICY.read_text())['library_sha256'])
        self.assertTrue(any(r['elf_address']==0xda03e4 for r in rows))
        self.assertLessEqual(len(rows),64)

    def test_ghidra_root_budget_accepts_the_selector_limit(self):
        source=Path('horizon/ui/ghidra/TraceShellBatch.java').read_text()
        self.assertIn('roots.size()>Math.min(64,cap)',source)
        self.assertIn('cap>96',source)
