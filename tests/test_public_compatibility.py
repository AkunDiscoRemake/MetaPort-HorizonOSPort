import json
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]

class PublicCompatibilityTests(unittest.TestCase):
    def setUp(self):
        self.p=json.loads((ROOT/'devices/compatibility-policy.json').read_text())
    def test_build_floor_matches_actual_adapters(self):
        gradle=(ROOT/'port/android/adapters/build.gradle').read_text()
        self.assertEqual(int(re.search(r'minSdk\s+(\d+)',gradle)[1]),self.p['adapter_build_baseline']['android_min_api'])
        # x86_64 is explicitly test-only; the default/release ABI remains ARM64.
        match=re.search(r"abiFilters\(emulatorTests == 'true' \? 'x86_64' : '([^']+)'\)",gradle)
        self.assertIsNotNone(match)
        self.assertEqual([match[1]],self.p['adapter_build_baseline']['abis'])
        self.assertIn("gradleProperty('metaportEmulatorTests').orElse('false')",gradle)
        self.assertIn("beforeVariants(selector().withBuildType('release'))",gradle)
        self.assertIn("if (emulatorTests == 'true') variant.enable = false",gradle)
    def test_planning_numbers_cannot_be_presented_as_validation(self):
        self.assertEqual(self.p['status'],'PRELIMINARY_NOT_DEVICE_VALIDATED')
        self.assertFalse(self.p['universal_compatibility_claimed'])
        self.assertFalse(self.p['functional_horizon_apk_available'])
        self.assertEqual(self.p['physically_validated_models'],[])
        self.assertFalse(self.p['planning_targets_not_measured_minima']['final_apk_size_and_peak_memory_measured'])
    def test_unsupported_features_are_not_fabricated(self):
        for f in ('six_dof','depth','passthrough'):
            self.assertTrue(self.p['features'][f]['unsupported_behavior'])
        for f in ('quest_hand_inference','meta_cloud'):
            self.assertEqual(self.p['features'][f]['current_status'],'NOT_PORTED')
        for v in self.p['deployment'].values(): self.assertFalse(v)
