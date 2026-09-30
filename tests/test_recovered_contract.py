"""Regression check against recorded original disassembly, NOT runtime conformance."""
import json
from pathlib import Path
import re
import unittest

ROOT=Path(__file__).resolve().parents[1]


class ContractEvidenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.contract=json.loads((ROOT/'horizon/tracking/abi/52168470052900520.json').read_text())
        analysis=json.loads((ROOT/'analysis/builds/52168470052900520/static-analysis.json').read_text())
        cls.source=next(e for e in analysis['partitions']['system_ext']['elf_analysis']
                        if e['path']==cls.contract['source_path'])

    def test_source_hash_bound_to_evidence(self):
        self.assertEqual(self.source['sha256'],self.contract['source_sha256'])
        self.assertEqual(self.source['disassembly_status'],'COMPLETE_TEXT_SECTION')

    def test_transaction_numbers_at_recorded_call_sites(self):
        assembly=self.source['disassembly']
        for tx in self.contract['transactions']:
            with self.subTest(method=tx['method']):
                line=re.search(r'^\s*'+tx['code_instruction_address']+r':.*$',assembly,re.M).group()
                self.assertRegex(line,r'mov\s+w1, #0x'+format(tx['code'],'x')+r'\b')
                call=re.search(r'^\s*'+tx['transact_call_address']+r':.*$',assembly,re.M).group()
                self.assertIn('AIBinder_transact@plt',call)

    def test_parcel_field_writers(self):
        for field in self.contract['MemoryAllocation']['fields_in_write_order']:
            line=re.search(r'^\s*'+field['write_call_address']+r':.*$',self.source['disassembly'],re.M).group()
            self.assertIn('AParcel_writeParcelFileDescriptor@plt' if field['native_object_offset']==0
                          else 'AParcel_writeInt32@plt',line)
        self.assertEqual(self.contract['runtime_bridge'],'NOT PORTED YET')
