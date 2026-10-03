# SPDX-License-Identifier: GPL-3.0-only
"""Recovered bookkeeping provenance, not execution of the original daemon."""
import hashlib
import json
from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parents[1]

class CurrentFocusEvidence(unittest.TestCase):
    def test_pid_index_uid_guard_and_set_operations(self):
        report=json.loads((ROOT/'analysis/builds/52168470052900520/focus-native-server.json').read_text())
        self.assertEqual(report['program_sha256'],'14289b0fca87a4b4fbcd1e0b1a06cd8035ebf8686551f86a3517ad08deaea418')
        functions={f['elf_address']:f['c'] for f in report['functions']}
        for offset,digest in {
            0x12bc0:'4a397772cfd522514efdf95b36210e94f0828b9fe63f215bdf4a824cf82a2b81',
            0x12de0:'8612955fd0d8cc9962387f52871ed8b3ab1901be2d98146f2a5b87b876b03127',
            0x25460:'150219ea64b3974b5d59e0fc1f02ea8809393be721b5b4ef58563b2e79021da3',
        }.items():
            self.assertEqual(hashlib.sha256(functions[offset].encode()).hexdigest(),digest)
        self.assertIn('ClientManager::addCurrentFocus',functions[0x12bc0])
        self.assertIn('ClientManager::removeCurrentFocus',functions[0x12de0])
        self.assertIn('__tree_balance_after_insert',functions[0x12bc0])
        self.assertIn('__tree_remove',functions[0x12de0])
        report=json.loads((ROOT/'analysis/android-runtime/focus-service-contracts.json').read_text())
        code=next(n for n in report['native_contracts'] if n['path']=='/bin/vrfocusserver')['disassembly']
        for instruction in ('12bfc:\tldrsw\tx9, [x21, #4]',
                            '12d20:\tldr\tw8, [x21]',
                            '12d24:\tldr\tw9, [x22, #24]',
                            '12d28:\tcmp\tw8, w9',
                            '12d2c:\tb.ne\t12db8',
                            '12f38:\tldr\tw8, [x21]',
                            '12f3c:\tldr\tw9, [x11, #24]',
                            '12f40:\tcmp\tw8, w9',
                            '12f44:\tb.ne\t12fec',
                            '263a4:\tblr\tx8'):
            self.assertIn(instruction,code)
