# SPDX-License-Identifier: GPL-3.0-only
import unittest
from handtracking.ai.prepare_optimizations import scan


class OptimizationTargets(unittest.TestCase):
    def scan(self, raw):
        return scan(b'X'*32+raw, f'[ 2] .rodata PROGBITS 00100000 000020 {len(raw):x}')

    def test_va_and_context_not_generic_activation(self):
        r = self.scan(b'generic quantization\0HandTracking uint8 input\0')
        rows = r['inference']['selected']
        self.assertTrue(rows[0]['hand_context_in_string'])
        self.assertEqual(rows[0]['address'], 0x100000+21)
        self.assertFalse(rows[1]['hand_context_in_string'])

    def test_bounds_and_missing_section(self):
        with self.assertRaises(ValueError): scan(b'', '')
        with self.assertRaises(ValueError): scan(b'', '[ 2] .rodata PROGBITS 10 20 30')

    def test_truncation_is_explicit(self):
        r = self.scan(b'quantization\0'*70)['inference']
        self.assertEqual(r['matched_count'], 70)
        self.assertEqual(len(r['selected']), 64)
        self.assertTrue(r['truncated'])
        self.assertEqual(len(r['candidates']), 70)
        self.assertEqual(r['candidates'][64]['address'],0x100000+64*13)

    def test_no_suffix_of_overlong_string(self):
        self.assertEqual(self.scan(b'x'*600+b' quantization\0')['inference']['matched_count'], 0)

    def test_camelcase_hand_detector_and_scheduler_context(self):
        r=self.scan(b'CNNVizardHandBboxDetector batchSize\0HandPrototypeTracking scheduling\0')
        self.assertTrue(r['inference']['selected'][0]['hand_context_in_string'])
        self.assertTrue(r['temporal']['selected'][0]['hand_context_in_string'])

    def test_roi_does_not_match_android(self):
        r=self.scan(b'android/content/Context\0ROI crop\0')
        self.assertEqual(r['temporal']['matched_count'],1)
        self.assertEqual(r['temporal']['selected'][0]['text'],'ROI crop')

    def test_roi_identifier_spellings_without_incidental_substrings(self):
        positive=['roiHeight','roi_width','QuantizedRoiAlign','RoIAlignForwardCPUKernel',
                  'maskedCamIds.size() * 4 == rois.size()','numROIs','HandROIExtractor']
        negative=['ANDROID_CONTEXT','android/content/Context','centroid_weights',
                  'data.numCentroids','Meroitic_Hieroglyphs','expectedGyroIndices_']
        r=self.scan(('\0'.join(positive+negative)+'\0').encode())
        self.assertEqual({x['text'] for x in r['temporal']['candidates']},set(positive))
