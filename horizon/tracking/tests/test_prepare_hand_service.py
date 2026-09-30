# SPDX-License-Identifier: GPL-3.0-only
import unittest
from horizon.tracking.prepare_hand_service import service_targets


class ServiceTargets(unittest.TestCase):
    def scan(self,raw):
        return service_targets(bytes(32)+raw,f'[ 3] .rodata PROGBITS 1000 20 {len(raw):x}')

    def test_prioritizes_real_policy_names_without_exclusive_claim(self):
        r=self.scan(b'buffer\0trackingPolicy\0wake_affine_controller\0')
        self.assertEqual(r['selected'][0]['text'],'trackingPolicy')
        self.assertEqual(r['selected'][0]['address'],0x1007)
        self.assertFalse(r['hand_exclusive']);self.assertFalse(r['runtime_activated'])

    def test_truncation_bounds_and_no_suffix_match(self):
        self.assertTrue(self.scan(b'thread\0'*130)['truncated'])
        self.assertEqual(self.scan(b'x'*600+b' hand\0')['matched_count'],0)
        with self.assertRaises(ValueError):service_targets(b'','')
        with self.assertRaises(ValueError):service_targets(b'','[ 3] .rodata PROGBITS 1000 20 30')
