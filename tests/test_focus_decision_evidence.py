# SPDX-License-Identifier: GPL-3.0-only
"""Static provenance/branch cross-checks, not an original firmware execution oracle."""
import hashlib
import json
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]

class FocusDecisionEvidence(unittest.TestCase):
    def test_pinned_decision_and_metadata_functions(self):
        report=json.loads((ROOT/'analysis/builds/52168470052900520/focus-native-server.json').read_text())
        self.assertEqual(report['program_sha256'],'14289b0fca87a4b4fbcd1e0b1a06cd8035ebf8686551f86a3517ad08deaea418')
        expected={
            0x25460:'150219ea64b3974b5d59e0fc1f02ea8809393be721b5b4ef58563b2e79021da3',
            0x265e0:'a7103a26bc07490d83161481f5946def95b17d79675e37e572034c2f21a36927',
            0x26ac0:'8ca63280a870927ef32c3946a84a5980b8a58e86a184514bec330a1cfe88d585',
            0x23cc0:'edfe65fa148d9e1d45e50fdec8fa4650bb9fdcbf55c524c3ca5d6981e8639792',
            0x21880:'f62559b8a0d3d1847e592cc66af851ac7edea86be344335d859e6762dbb5585e',
            0x21b20:'3939fa043bb582eee967adb03dc61bc0db13b888cc73f8903298907ad793ec47'}
        functions={f['elf_address']:f['c'] for f in report['functions']}
        for address,digest in expected.items():
            self.assertEqual(hashlib.sha256(functions[address].encode()).hexdigest(),digest)
        self.assertIn('Background Access:',functions[0x23cc0])
        self.assertIn('grantTrackingServiceAccess: displayId: %d',functions[0x21880])
        self.assertIn('revokeTrackingServiceAccess: displayId: %d',functions[0x21b20])
        self.assertIn('*(int *)(p_Var15 + 0x24) != (int)local_e0',functions[0x25460])
        self.assertIn('this[0xa8]',functions[0x25460])
    def test_key_branches_have_instruction_evidence(self):
        report=json.loads((ROOT/'analysis/android-runtime/focus-service-contracts.json').read_text())
        original=next(r for r in report['native_contracts'] if r['path']=='/bin/vrfocusserver')
        self.assertEqual(original['sha256'],'14289b0fca87a4b4fbcd1e0b1a06cd8035ebf8686551f86a3517ad08deaea418')
        asm=original['disassembly']
        for instruction in ('25b2c:\tldr\tw10, [x21, #36]',
                            '25b30:\tcmp\tw10, w8',
                            '260cc:\tldr\tx8, [x21, #96]',
                            '260f0:\tcmp\tw9, w20',
                            '26350:\tstr\tw9, [x8, #8]',
                            '26358:\tstrb\tw9, [x8, #12]'):
            self.assertIn(instruction,asm)

    def test_exact_connection_vtable_binds_each_input_feed(self):
        report=json.loads((ROOT/'analysis/builds/52168470052900520/focus-native-server.json').read_text())
        slots=report['connection_manager_vtable']
        expected={2:(0x21540,'getClientsWithForegroundActivity'),
                  3:(0x21590,'getClientsCurrentlyRendering'),
                  4:(0x215e0,'getClientWithWindowFocus'),
                  5:(0x21600,'getClientsWithTopActivities'),
                  6:(0x21740,'getAllClientsWithTopActivities')}
        self.assertEqual([row['slot'] for row in slots],list(range(7)))
        functions={f['elf_address']:f['name'] for f in report['functions']}
        for slot,(offset,name) in expected.items():
            row=slots[slot]
            self.assertTrue(row['target_is_executable']);self.assertTrue(row['exact_function_entry'])
            self.assertEqual(row['slot_elf_address'],0x38928+slot*8)
            self.assertEqual(row['target_elf_address'],offset)
            self.assertEqual(row['resolved_elf_address'],offset)
            self.assertEqual(row['resolved_name'],name);self.assertEqual(functions[offset],name)
