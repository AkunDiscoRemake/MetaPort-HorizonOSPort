# SPDX-License-Identifier: GPL-3.0-only
import json
from pathlib import Path
import unittest

class BatchReferenceTests(unittest.TestCase):
    def test_additional_frame_callbacks_are_referenced(self):
        p=Path('analysis/builds/52168470052900520')
        r=json.loads((p/'shell-frame-decompilation.json').read_text())
        for address,caller in ((0xd8a5e8,0xd8a56c),(0xce43c4,0xd622fc),(0xd8ec48,0xd622fc)):
            matches=[f for f in r['functions'] if f['elf_address']==caller]
            self.assertEqual(len(matches),1)
            self.assertIn(f'FUN_{address+int(r["image_base"],16):08x}',matches[0]['c_like'])
    def test_known_timeout_preserved_as_failure_not_success(self):
        r=json.loads(Path('analysis/builds/52168470052900520/shell-frame-decompilation.json').read_text())
        f=next(f for f in r['functions'] if f['elf_address']==0xdc8480)
        self.assertEqual(f['status'],'DECOMPILATION_FAILED')
        self.assertIn('timeout',f['diagnostic'])
