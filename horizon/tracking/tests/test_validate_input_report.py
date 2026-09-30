# SPDX-License-Identifier: GPL-3.0-only
import unittest
from horizon.tracking.prepare_input import ENGINE_SHA
from horizon.tracking.validate_input_report import validate


def fixture(reason):
    return {'program_sha256':ENGINE_SHA,'firmware_executed':False,'abi_validated':False,
            'functions':[{'name':f'fn{i}','elf_address':addr,'status':'DECOMPILED_NOT_VALIDATED',
                          'c_like':'synthetic test text','selection_evidence':reason}
                         for i,addr in enumerate((0x1620ce0,0x16222a0,0x162bee0))],
            'pointer_windows':[{'candidate_function':'fn2','candidate_abi_validated':False}]}


class InputEvidenceTests(unittest.TestCase):
    def test_direct_and_relocated_pointer_evidence_are_both_valid(self):
        for reason in ('Pointer reference at observed address point', 'Executable pointer candidate'):
            r=validate(fixture(reason))
            self.assertEqual(r['decompiled_pointer_candidates'],1)
            self.assertFalse(r['private_abi_validated'])

    def test_human_description_is_not_validation_key(self):
        self.assertEqual(validate(fixture('renamed description'))['selected_functions'],3)

    def test_reject_wrong_identity_missing_executor_and_runtime_claim(self):
        for key,value in (('program_sha256','0'*64),('abi_validated',True),('firmware_executed',True)):
            r=fixture('');r[key]=value
            with self.assertRaises(ValueError):validate(r)
        r=fixture('');r['functions'][2]['status']='DECOMPILATION_FAILED'
        with self.assertRaises(ValueError):validate(r)

    def test_reject_pointer_mismatch_and_duplicate_function(self):
        r=fixture('');r['pointer_windows'][0]['candidate_function']='absent'
        with self.assertRaises(ValueError):validate(r)
        r=fixture('');r['functions'].append(r['functions'][0])
        with self.assertRaises(ValueError):validate(r)
