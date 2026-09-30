# SPDX-License-Identifier: GPL-3.0-only
import unittest
from horizon.tracking.hvx_evidence import HvxEvidence,operand_form


class HvxForms(unittest.TestCase):
    def test_preserves_signedness_and_pair_shape(self):
        a='1000: v0.w += vrmpy(v1.ub,r2.b)'
        b='1004: v4.w += vrmpy(v5.ub,r6.b)'
        self.assertEqual(operand_form(a),operand_form(b))
        self.assertNotEqual(operand_form(a),operand_form(b.replace('r6.b','r6.ub')))
        self.assertNotEqual(operand_form(a),operand_form(b.replace('v4.w','v5:4.w')))

    def test_count_and_context_are_bounded(self):
        evidence=HvxEvidence()
        for i in range(32):evidence.feed(f'{0x1000+i*4:x}: v0.w = vrmpy(v1.ub,r2.b) #{i}')
        r=evidence.report()
        self.assertEqual(len(r['operand_forms']['vrmpy']),16)
        self.assertEqual(r['unretained_form_occurrences']['vrmpy'],16)
        self.assertEqual(len(r['instruction_windows']),2)
        self.assertTrue(r['instruction_windows'][0]['context_truncated'])
        self.assertFalse(r['hand_kernel_identified'])

    def test_context_does_not_claim_complete_function(self):
        e=HvxEvidence()
        for i in range(8):e.feed(f'{i*4:x}: r0 = #0')
        e.feed('20: v0 = vlut16(v1,v2)')
        for i in range(8):e.feed(f'{36+i*4:x}: r0 = #0')
        w=e.report()['instruction_windows'][0]
        self.assertEqual(len(w['listing']),17)
        self.assertFalse(w['context_truncated'])
