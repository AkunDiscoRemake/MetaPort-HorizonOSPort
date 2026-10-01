# SPDX-License-Identifier: GPL-3.0-only
import json
import unittest
from horizon.ui.prepare_shell_platform_runtime import EVIDENCE,TARGETS

class PlatformRuntimeReferences(unittest.TestCase):
    def test_core_calls_exist_in_pinned_startup_body(self):
        r=json.loads(EVIDENCE.read_text());base=int(r['image_base'],16)
        self.assertEqual(len(TARGETS),4)
        for address,caller,_ in TARGETS:
            f=next(f for f in r['functions'] if f['elf_address']==caller)
            self.assertTrue(f'FUN_{address+base:08x}' in f['c_like'],hex(address))
