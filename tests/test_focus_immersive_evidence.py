# SPDX-License-Identifier: GPL-3.0-only
"""Pinned selection/history evidence; no claim of an original runtime oracle."""
import hashlib
import json
from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parents[1]

class ImmersiveEvidence(unittest.TestCase):
    def test_selection_helpers_are_pinned(self):
        report=json.loads((ROOT/'analysis/builds/52168470052900520/focus-native-server.json').read_text())
        self.assertEqual(report['program_sha256'],'14289b0fca87a4b4fbcd1e0b1a06cd8035ebf8686551f86a3517ad08deaea418')
        functions={f['elf_address']:f['c'] for f in report['functions']}
        expected={
            0x13400:'f1c7e6290dc51087fa8775debe73c092d4b353dbaaf2cf9a28c1382f75ffa7d9',
            0x22f40:'ad677a01a634e99abfece16498e6736103173b5239c979a5a8b2abf982e1b1b9',
            0x23b60:'ca7c5b9df6079db9ed1bebcc26fc12c161d5b5ae1195008408bd4fac46ce5f48',
            0x26760:'58eb34fe65ca6daeee0e4e798388f5625163df715278b4a7c6bdd0612bd21268',
            0x27d70:'02b47493e25f44f35b7a3ce404ba50ce18c3f22902f2a77cf34603ab4bc85d1c',
            0x27f50:'6650fb5580b8b8260e90c765968a532ce49318052bb14e787fcee602e32b6c12',
            0x28080:'e5ed102820e35e69d275546b187897d2c34a0147ee22b5dc0edf58bf34f74991',
            0x282e0:'d3ba5c357d33c6edeeeedcb81988f84c59a3513d65201d979ce457091f897038'}
        for offset,digest in expected.items():
            self.assertEqual(hashlib.sha256(functions[offset].encode()).hexdigest(),digest)
        self.assertIn('Process::isProcessAlive',functions[0x13400])
        self.assertIn('if (10 < uVar5)',functions[0x28080])
        self.assertIn('Process::getProcessName(param_1,true)',functions[0x27f50])
        for name in ('system_server','com.oculus.vralertservice','com.oculus.os.vrlockscreen','com.android.settings'):
            self.assertIn('"'+name+'"',functions[0x27d70])
    def test_arm64_confirms_boolean_and_window_pid_not_uid(self):
        report=json.loads((ROOT/'analysis/android-runtime/focus-service-contracts.json').read_text())
        native=next(r for r in report['native_contracts'] if r['path']=='/bin/vrfocusserver')
        self.assertEqual(native['sha256'],'14289b0fca87a4b4fbcd1e0b1a06cd8035ebf8686551f86a3517ad08deaea418')
        code=native['disassembly']
        for instruction in ('27dc4:\tcset\tw0, ne',
                            '23084:\tlsr\tx8, x0, #32',
                            '23088:\tcmp\tw26, w8',
                            '230cc:\ttbnz\tw27, #0, 23358',
                            '23228:\ttbnz\tw27, #0, 23358',
                            '2330c:\tadr\tx8, 7d9f',
                            '2331c:\tbl\t282e0',
                            '23450:\tadr\tx1, 7d9f',
                            '23458:\tbl\t35a10',
                            '280fc:\tcmp\tw8, w9'):
            self.assertIn(instruction,code)
