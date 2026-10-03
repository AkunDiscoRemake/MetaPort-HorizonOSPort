# SPDX-License-Identifier: GPL-3.0-only
import struct
import unittest
from horizon.ui.trace_arm64_tail import trace_tail
from horizon.ui.tests import test_shell_abi

class TailTests(unittest.TestCase):
    def blob(self,words):
        b,_=test_shell_abi.ReturnProofTests().fixture()
        for i,word in enumerate(words):struct.pack_into('<I',b,256+4*i,word)
        return b
    def test_both_branch_directions_and_cycle(self):
        b=self.blob([0x14000001,0x17ffffff])
        r=trace_tail(b,0x1000,'')
        self.assertEqual(r['status'],'CYCLE')
        self.assertEqual(r['steps'][1]['target'],0x1000)
    def test_plt_import_is_not_runtime_binding(self):
        b=self.blob([0xb0000010,0xf9400611,0x91002210,0xd61f0220])
        r=trace_tail(b,0x1000,'2008 000000000 R_AARCH64_JUMP_SLOT 000000000 free + 0')
        self.assertEqual(r['status'],'IMPORTED_SYMBOL')
        self.assertEqual(r['symbol'],'free')
        self.assertFalse(r['runtime_binding_verified'])
        self.assertEqual(trace_tail(b,0x1000,'')['status'],'NO_UNIQUE_JUMP_SLOT')
    def test_does_not_follow_calls_or_unmapped_targets(self):
        self.assertEqual(trace_tail(self.blob([0x94000001]),0x1000,'')['status'],'UNSUPPORTED_BODY')
        self.assertEqual(trace_tail(self.blob([0x14000100]),0x1000,'')['status'],'UNMAPPED_TARGET')
    def test_budget(self):
        self.assertEqual(trace_tail(self.blob([0x14000001]),0x1000,'',1)['status'],'BUDGET_EXHAUSTED')
