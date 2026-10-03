# SPDX-License-Identifier: GPL-3.0-only
import json
import unittest
from horizon.ui.prepare_shell_frames import TARGETS, EVIDENCE

class FrameReferenceTests(unittest.TestCase):
    def test_all_candidates_have_original_reference_evidence(self):
        r=json.loads(EVIDENCE.read_text());base=int(r['image_base'],16)
        self.assertLessEqual(len(TARGETS),8)
        self.assertEqual(len({a for a,_,_ in TARGETS}),len(TARGETS))
        for address,caller,_ in TARGETS:
            matches=[f for f in r['functions'] if f['elf_address']==caller]
            self.assertEqual(len(matches),1)
            self.assertIn(f'FUN_{address+base:08x}',matches[0]['c_like'])
