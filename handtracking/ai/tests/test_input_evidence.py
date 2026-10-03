import json
from pathlib import Path
import unittest

class OriginalInputEvidenceTests(unittest.TestCase):
    def test_original_joypad_signature_and_axes_match_captured_call_site(self):
        c=json.loads(Path('horizon/input/original-contract.json').read_text())
        r=json.loads(Path('analysis/builds/52168470052900520/ui-decompilation.json').read_text())
        apk=next(a for a in r['applications'] if a['path']=='/priv-app/VrShell/VrShell.apk')
        self.assertEqual(c['vr_shell_sha256'],apk['sha256'])
        self.assertEqual(c['libshell_sha256'],next(n for n in apk['native_libraries'] if n['apk_member']=='lib/arm64-v8a/libshell.so')['sha256'])
        evidence=c['joypad']['evidence']
        self.assertIn(evidence,apk['input_call_sites'])
        for arg in c['joypad']['arguments'][:6]:
            self.assertIn('getAxisValue(%d)'%arg['android_axis'],evidence['context'])
        self.assertIn('nativeJoypadAxis(axisValue5, axisValue6, axisValue7, axisValue8, axisValue9, axisValue10, deviceId3)',evidence['context'])
        self.assertFalse(c['runtime_validated'])
        self.assertFalse(c['joypad']['quest_controller_enumeration'])

    def test_native_version_evidence_does_not_claim_runtime_abi(self):
        c=json.loads(Path('horizon/input/original-contract.json').read_text())['native_versions_observed']
        root=Path('analysis/builds/52168470052900520')
        engine=json.loads((root/'hand-decompilation.json').read_text())
        client=json.loads((root/'hand-client-decompilation.json').read_text())
        self.assertEqual(c['engine_sha256'],engine['program_sha256'])
        self.assertEqual(c['client_sha256'],client['program_sha256'])
        functions={f.get('name'):f for f in engine['functions']+client['functions']}
        self.assertIn('return 0x24;',functions['capabilityRegistryGetAbiVersion']['c_like'])
        self.assertEqual(c['registry_abi'],0x24)
        for version in c['hand_tracker_factory_versions']:
            self.assertIn('case 0x%x:'%version,functions['createHandTrackerFbs']['c_like'])
        self.assertFalse(c['types_vtables_payloads_validated'])
