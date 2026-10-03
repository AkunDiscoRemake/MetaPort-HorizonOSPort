# SPDX-License-Identifier: GPL-3.0-only
"""The session set feeds rendering, not foreground activities or grants."""
import hashlib
import json
from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parents[1]

class SessionBindingEvidence(unittest.TestCase):
    def test_rendering_getter_and_session_updates_share_set_170(self):
        report=json.loads((ROOT/'analysis/builds/52168470052900520/focus-native-server.json').read_text())
        self.assertEqual(report['program_sha256'],'14289b0fca87a4b4fbcd1e0b1a06cd8035ebf8686551f86a3517ad08deaea418')
        functions={f['elf_address']:f for f in report['functions']}
        for offset,digest in {
            0x21590:'d7ca081b903a12841bb0cea2b25a1f9a802b2479c266fdd4e65081f384d6300d',
            0x22510:'6c06f84c534dc9282d271c55c8ba9678e5d34b580b63b2ee8c6e4854ba8f35f5',
        }.items():
            self.assertEqual(hashlib.sha256(functions[offset]['c'].encode()).hexdigest(),digest)
        self.assertEqual(functions[0x21590]['name'],'getClientsCurrentlyRendering')
        native=json.loads((ROOT/'analysis/android-runtime/focus-service-contracts.json').read_text())
        server=next(n for n in native['native_contracts'] if n['path']=='/bin/vrfocusserver')
        self.assertEqual(server['sha256'],report['program_sha256'])
        for instruction in ('215b0:\tadd\tx1, x0, #0x170',
                            '215bc:\tb\t21de0',
                            '22580:\tadd\tx0, x19, #0x170',
                            '225a0:\tb\t20a60',
                            '225d4:\tadd\tx22, x19, #0x170',
                            '225e8:\tbl\t20bc0'):
            self.assertIn(instruction,server['disassembly'])
