import json
from pathlib import Path
import unittest

class NativeUiEvidenceTests(unittest.TestCase):
    def setUp(self):
        root=Path('analysis/builds/52168470052900520')
        self.base=json.loads((root/'shell-hzos-native.json').read_text())
        self.spaces=json.loads((root/'shell-hzos-spaces-native.json').read_text())
    def test_reports_match_selected_original_libraries(self):
        policy=json.loads(Path('horizon/ui/platform-native-policy.json').read_text())
        for lib,r in zip(policy['libraries'],[self.base,self.spaces]):
            self.assertEqual(r['program_sha256'].lower(),lib['sha256'])
            self.assertFalse(r['firmware_executed'])
            for name in lib['exports']:
                f=next(f for f in r['functions'] if f.get('name')==name.split('@@')[0])
                self.assertEqual(f['status'],'DECOMPILED_NOT_VALIDATED')
    def test_space_service_is_real_dependency_not_a_local_matrix_api(self):
        f=next(f for f in self.spaces['functions'] if f.get('name')=='HzuSpaceManager_create')
        self.assertIn('horizonos.spaces.spacemanager.ISpaceManager',f['c_like'])
        self.assertIn('HzuFpHalBroker_getService',f['c_like'])
        locate=next(f for f in self.spaces['functions'] if f.get('name')=='HzuSpaceManager_locateSpace')
        self.assertTrue(any(c['name']=='toHzuSpaceData' for c in locate['direct_callees']))
    def test_presentation_requires_original_surface_and_looper(self):
        f=next(f for f in self.base['functions'] if f.get('name')=='HzuChoreographer_create')
        self.assertIn('No looper prepared for thread',f['c_like'])
        self.assertIn('No surface control associated with window',f['c_like'])
        layer=next(f for f in self.base['functions'] if f.get('name')=='HzuStrataLayer_setBuffer')
        self.assertTrue(any(c['name']=='convertToHardwareBuffer' for c in layer['direct_callees']))
