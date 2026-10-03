# SPDX-License-Identifier: GPL-3.0-only
"""Pin OVR::OS::VrFocusService (0x29210..0x2dd60) evidence and verify VrFocusService.java."""
import hashlib
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class FocusServiceEvidenceTests(unittest.TestCase):
    def test_pinned_vrfocusservice_functions_and_java_implementation(self):
        report = json.loads(
            (ROOT / 'analysis/builds/52168470052900520/focus-native-server.json').read_text()
        )
        self.assertEqual(
            report['program_sha256'],
            '14289b0fca87a4b4fbcd1e0b1a06cd8035ebf8686551f86a3517ad08deaea418',
        )
        expected = {
            0x2A040: '196b57cf8b6889ee3917241162e385d3ddf3f3bc8fc3f84b30ecbff9adc45a49',
            0x2A7E0: '1b0d3fa778178f78555ced88aa53261f9050d4c9632a4581413e2fc44efc8959',
            0x2B6C0: '18fb67bd0e32e37d3bd489fa0d8961e4ab2161d918ef0b8de2da7e7a16ade94a',
            0x2C450: 'e2baa7205e3a0a74db49a009025d8f944e682073e2a524ba3da7593071c5cf89',
            0x2C660: '72b3a23949e6c0eaaab160312e43892c34272e7e1568ff5891aee15f33dae751',
            0x2C820: '08b35e7669ad4bde54223f962dd59237fcb4852166db71e6af63d9e7856a2fb1',
            0x2C960: '7c7d2321d0ff561ac89626b8aceab4083eb7c52f2f5875e22aaf553f63a9f330',
            0x2CB90: '033fe1d80fa1281e9d867d00c10f39d560be05f6f7ec1a75f6b3c0f29929eabd',
            0x2CCC0: '751af07ea31c05f2104922bc13474b59c909128296a2a0f750d4aed18cfd74d9',
        }
        functions = {f['elf_address']: f['c'] for f in report['functions']}
        for address, digest in expected.items():
            self.assertEqual(hashlib.sha256(functions[address].encode()).hexdigest(), digest)

        # 0x2a7e0 notifyTopActivityListeners calls FocusPolicy vtable[3] (getTopActivity) and vtable[2] (getImmersiveApp).
        self.assertIn('(*(code *)ppuVar6[3])(&local_c8,puVar5)', functions[0x2A7E0])
        self.assertIn('(*(code *)ppuVar6[2])(&local_c0,puVar5)', functions[0x2A7E0])
        # 0x2c660 getImmersiveApp returns -4 (EX_NULL_POINTER) when nullopt.
        self.assertIn('fromExceptionCode(-4', functions[0x2C660])
        # 0x2c450 setAppState checks callingPid == pid and notifies top activity on state 0 or 2.
        self.assertIn('getCallingPid()', functions[0x2C450])
        self.assertIn('notifyTopActivityListeners(this)', functions[0x2C450])

        service_java = (
            ROOT / 'port/android/adapters/src/main/java/org/metaport/port/focus/VrFocusService.java'
        ).read_text()
        self.assertIn('horizonos.permission.READ_FOCUS_STATE', service_java)
        self.assertIn('horizonos.permission.GRANT_TRACKING_SERVICE_ACCESS_TO_DISPLAY', service_java)
        self.assertIn('new ImmersiveApp("", 0, 0, false)', service_java)
        self.assertIn('ServiceDirectory.publish(FocusWire.NAME, endpoint)', service_java)
