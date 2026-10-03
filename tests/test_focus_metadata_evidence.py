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
            0x12bc0:'4a397772cfd522514efdf95b36210e94f0828b9fe63f215bdf4a824cf82a2b81',
            0x12de0:'8612955fd0d8cc9962387f52871ed8b3ab1901be2d98146f2a5b87b876b03127',
            0x13400:'f1c7e6290dc51087fa8775debe73c092d4b353dbaaf2cf9a28c1382f75ffa7d9',
        }.items():
            self.assertEqual(hashlib.sha256(functions[offset].encode()).hexdigest(),digest)
        header=(ROOT/'port/android/adapters/src/main/cpp/focus_client_metadata.hpp').read_text()
        for name in ('horizonos.permission.ACCESS_BACKGROUND_HEAD_TRACKING',
                     'horizonos.permission.ACCESS_BACKGROUND_INPUT_TRACKING'):
            self.assertIn('"'+name+'"',functions[0xf0d0])
            self.assertIn('"'+name+'"',(ROOT/'port/android/adapters/src/main/java/org/metaport/port/focus/AppProcessMetadataBackend.java').read_text())
            self.assertIn('"'+name+'"',header)
        for token in ('"com.oculus.systemdriver"',
                      '"/system/bin/audioserver"','"/system_ext/bin/mrsystemservice"',
                      '"android.uid.system:1000"'):
            self.assertIn(token,functions[0xf0d0])
            self.assertIn(token,header)
        for sso_hex,plain in (('0x687372762e7375','"com.oculus.vrshell"'),
                              ('0x726175672e7375','"com.oculus.guardian"'),
                              ('0x6574737973','"system_server"')):
            self.assertIn(sso_hex,functions[0xf0d0])
            self.assertIn(plain,header)
        for call in ('getProcessUid','getProcessName','getPackagesForUid','checkPermission'):
            self.assertIn(call,functions[0x10aa0])
        self.assertIn('__erase_unique<int>',functions[0x118e0])
        self.assertIn('Process::getProcessName(*piVar12,true)',functions[0x118e0])
        self.assertIn('Process::isProcessAlive',functions[0x13400])
        contracts=json.loads((ROOT/'analysis/android-runtime/focus-service-contracts.json').read_text())
        disasm=next(r for r in contracts['native_contracts'] if r['path']=='/bin/vrfocusserver')['disassembly']
        for snippet in ('10c04:\tbl\t35a60 <OVR::OS::Process::getProcessName(int, bool)@plt>',
                        '11a60:\tbl\t35a60 <OVR::OS::Process::getProcessName(int, bool)@plt>',
                        '11af8:\tmov\tx1, x21'):
            self.assertIn(snippet,disasm)
