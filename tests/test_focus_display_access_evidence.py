# SPDX-License-Identifier: GPL-3.0-only
"""Evidence for display tracking access, permission bypass, and activity/display classification."""
import hashlib
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class DisplayAccessEvidence(unittest.TestCase):
    def test_original_display_access_and_activity_classification_contracts(self):
        report = json.loads((ROOT / 'analysis/builds/52168470052900520/focus-native-server.json').read_text())
        self.assertEqual(report['program_sha256'], '14289b0fca87a4b4fbcd1e0b1a06cd8035ebf8686551f86a3517ad08deaea418')
        functions = {f['elf_address']: f['c'] for f in report['functions']}
        for offset, digest in {
            0xf5e0: 'aec143dbc10b858b5af271ccced030c37056181d062b05edddc6901d15a63805',
            0x15480: '76a3b4c142ececdb1fbfa58ce4ea1bac330193e44e2966f6f69e71dcf7b023fe',
            0x182e0: 'f524e7f6ee30b877bdad37553c4ec5017a370b2fff09abeb9f790e3b0bd5ec2c',
            0x20860: '92576bdeb7ffe1854f16c4d92fde15a8bdb382ef6a30e417159b6271b00c46e8',
            0x20cc0: 'e3cc5e035553925f853fb4627972899410669214df0e3f121a3815fea4e36e66',
            0x21540: '1767f75063661b304fdbd3effd4bbf1d264d77b650f00a44935f9983ce796c62',
            0x21590: 'd7ca081b903a12841bb0cea2b25a1f9a802b2479c266fdd4e65081f384d6300d',
            0x215e0: '582f22b1c5cc8a756b3ce5378a72131f016a21bc8fb3566cc13607b5196ec67a',
            0x21600: '74f8f30c15c9ced6162536a6c830493b0cd37f1d23bee24c08dbe87fee7b1601',
            0x21740: '225a4657e7272091c625974f1a6d7c31b3f25be1ea50b264f499493c1f1ab4e6',
            0x21880: 'f62559b8a0d3d1847e592cc66af851ac7edea86be344335d859e6762dbb5585e',
            0x21b20: '3939fa043bb582eee967adb03dc61bc0db13b888cc73f8903298907ad793ec47',
            0x22d50: 'f66c7e0d6067d203c34c43bd28edb643fac1b00be38eb343cf7c99bdf301fd29',
            0x265d0: '09b975af0045ae2008c1fa2ed432b0a890736f4760b3ee817ef3be025113224f',
            0x2cb90: '033fe1d80fa1281e9d867d00c10f39d560be05f6f7ec1a75f6b3c0f29929eabd',
            0x2ccc0: '751af07ea31c05f2104922bc13474b59c909128296a2a0f750d4aed18cfd74d9',
            0x2dd60: '5e5eb9fbd289926752f7c2e038fb0edd94941e96202d0f4683187651b8b46e74',
            0x2ff60: '02ab147401f93b0a6f6295dd60229ec758894c943ec6a3b9e614b4ce1affd0d4',
        }.items():
            self.assertEqual(hashlib.sha256(functions[offset].encode()).hexdigest(), digest)

        header = (ROOT / 'port/android/adapters/src/main/cpp/focus_display_access.hpp').read_text()
        for perm in (
            '"horizonos.permission.READ_FOCUS_STATE"',
            '"android.permission.DUMP"',
            '"horizonos.permission.GRANT_TRACKING_SERVICE_ACCESS_TO_DISPLAY"',
        ):
            self.assertIn(perm, functions[0xf5e0])
            self.assertIn(perm, header)

        contracts = json.loads((ROOT / 'analysis/android-runtime/focus-service-contracts.json').read_text())
        disasm = next(r for r in contracts['native_contracts'] if r['path'] == '/bin/vrfocusserver')['disassembly']
        for snippet in (
            '15bfc:\tstr\twzr, [x0, #28]',
            '182f8:\tcmp\tw2, #0x3',
            '20f74:\tmov\tw24, #0x1',
            '218c8:\tcbz\tw21, 21a68',
            '21960:\tcmp\tx8, #0x2',
            '21a14:\tmov\tw2, #0x2',
            '21b44:\tcbz\tw1, 21d4c',
            '21c40:\tcmp\tx8, #0x1',
            '2dd78:\tcbz\tw0, 2de38',
        ):
            self.assertIn(snippet, disasm)
