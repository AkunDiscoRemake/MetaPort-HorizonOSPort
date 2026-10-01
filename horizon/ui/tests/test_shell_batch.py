# SPDX-License-Identifier: GPL-3.0-only
import json
from pathlib import Path
import unittest

class BatchReferenceTests(unittest.TestCase):
    def test_additional_frame_callbacks_are_referenced(self):
        p=Path('analysis/builds/52168470052900520')
        r=json.loads((p/'shell-frame-decompilation.json').read_text())
        for address,caller in ((0xd8a5e8,0xd8a56c),(0xbe43c4,0xd622fc),(0xd8ec48,0xd622fc)):
            matches=[f for f in r['functions'] if f['elf_address']==caller]
            self.assertEqual(len(matches),1)
            self.assertTrue(f'FUN_{address+int(r["image_base"],16):08x}' in matches[0]['c_like'], hex(address))
    def test_failed_decompilation_has_diagnostic_not_invented_source(self):
        r=json.loads(Path('analysis/builds/52168470052900520/shell-frame-decompilation.json').read_text())
        f=next(f for f in r['functions'] if f['elf_address']==0xdc8480)
        if f['status']=='DECOMPILATION_FAILED':
            self.assertTrue(f['diagnostic'])
            self.assertFalse(f.get('c_like'))
        else:
            self.assertEqual(f['status'],'DECOMPILED_NOT_VALIDATED')
            self.assertTrue(f['c_like'])
