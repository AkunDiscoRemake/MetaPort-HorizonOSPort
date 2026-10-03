# SPDX-License-Identifier: GPL-3.0-only
"""Pin the inferred native evidence; not an original-binary behavioral oracle."""
import hashlib
import json
from pathlib import Path
import unittest

class FocusListenerEvidence(unittest.TestCase):
    def test_pinned_listener_functions(self):
        root=Path(__file__).resolve().parents[1]
        report=json.loads((root/'analysis/builds/52168470052900520/focus-native-server.json').read_text())
        self.assertEqual(report['program_sha256'],'14289b0fca87a4b4fbcd1e0b1a06cd8035ebf8686551f86a3517ad08deaea418')
        expected={
            0x2a620:'3711afe4ed3e3f963bd75f2fa00007d704da620405225b64241c4cad245f2471',
            0x2ab10:'7aaa9f469bde27bff7cb558c82cbc266d117ce707d7a4e53789250985aeab59c',
            0x2acc0:'03a4346f1bba9a522ad49c48b2b1ca8050be7d7286cf35c674c74aad8f52f52b',
            0x2b8a0:'111638122b0e802e95103e14133ca8dbb05620cb21480444f8d81b261f6d9605',
            0x2bd40:'2ad2f689d2ff19c6890d6eeb9c9c635c29864b7bb02c9fb1cc38baa533024c7d',
            0x2bf40:'3f9222494fee523f4494ac031eb6971af0a609c3958c1d9b7b038a322d1eefdc',
            0x2c320:'c5f7ba6ef14c579bc2193b0550de691b9af5d1aba899388713a614e5bf0e2c36'}
        functions={f['elf_address']:f['c'] for f in report['functions']}
        for address,digest in expected.items():
            self.assertEqual(hashlib.sha256(functions[address].encode()).hexdigest(),digest)
        self.assertIn('(uint)param_2 < 2',functions[0x2b8a0])
        self.assertIn('uVar2 = *(undefined4 *)(pVVar8 + 0x20)',functions[0x2a620])
        self.assertNotIn('computeFocusState',functions[0x2a620])
        for address in (0x2b8a0,0x2bf40):
            self.assertNotIn('notifyListeners(',functions[address])
            self.assertNotIn('notifyTopActivityListeners(',functions[address])
