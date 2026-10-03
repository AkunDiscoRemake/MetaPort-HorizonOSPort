# SPDX-License-Identifier: GPL-3.0-only
"""Original metadata dependencies; public Android reader is not the original cache."""
import hashlib
import json
from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parents[1]

class MetadataEvidence(unittest.TestCase):
    def test_original_metadata_dependencies(self):
        report=json.loads((ROOT/'analysis/builds/52168470052900520/focus-native-server.json').read_text())
        self.assertEqual(report['program_sha256'],'14289b0fca87a4b4fbcd1e0b1a06cd8035ebf8686551f86a3517ad08deaea418')
        functions={f['elf_address']:f['c'] for f in report['functions']}
        for offset,digest in {
            0xf0d0:'7d382e3a9b39a909e6118c1a09fdf08080e99adf9d5a0481d1b133db39ad0f5d',
            0x10aa0:'006a9c0c93cce0120fa9bd59519eac7e4b7661ac6afdb029cfa87dfd7940f118',
            0x118e0:'7616b5a40a8f939137a58bc5da734aab4c43ad99cc9fa5f39e9db9d2062d7232',
        }.items():
            self.assertEqual(hashlib.sha256(functions[offset].encode()).hexdigest(),digest)
        for name in ('horizonos.permission.ACCESS_BACKGROUND_HEAD_TRACKING',
                     'horizonos.permission.ACCESS_BACKGROUND_INPUT_TRACKING'):
            self.assertIn('"'+name+'"',functions[0xf0d0])
            self.assertIn('"'+name+'"',(ROOT/'port/android/adapters/src/main/java/org/metaport/port/focus/AppProcessMetadataBackend.java').read_text())
        for call in ('getProcessUid','getProcessName','getPackagesForUid','checkPermission'):
            self.assertIn(call,functions[0x10aa0])
        self.assertIn('__erase_unique<int>',functions[0x118e0])
        self.assertIn('Process::getProcessName(*piVar12,true)',functions[0x118e0])
