# SPDX-License-Identifier: GPL-3.0-only
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile
from handtracking.distribution.package import build, verify, safe_name, MANIFEST, expected_originals

class PackageTests(unittest.TestCase):
    def test_paths(self):
        for name in ('../escape','/absolute','a/../b','a\\b','C:x','a//b','./a'):
            with self.assertRaises(ValueError):safe_name(name)
        self.assertEqual(safe_name('handtracking/native/include/test.hpp'),'handtracking/native/include/test.hpp')

    def test_source_roundtrip_and_tampering(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);source=root/'file';source.write_text('source')
            archive=root/'bundle.zip'
            with patch('handtracking.distribution.package.source_files',return_value={'README.md':source}):
                build(archive)
            m=verify(archive);self.assertFalse(m['inference_ported']);self.assertEqual(m['original_model_file_count'],0)
            self.assertTrue(archive.with_suffix('.zip.sha256').exists())
            with zipfile.ZipFile(archive) as z:manifest=z.read(MANIFEST)
            with zipfile.ZipFile(archive,'w') as z:
                z.writestr(MANIFEST,manifest);z.writestr('README.md','tampered')
            with self.assertRaises(ValueError):verify(archive)

    def test_manifest_cannot_hide_missing_models_or_overclaim(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);source=root/'file';source.write_text('source');archive=root/'bundle.zip'
            with patch('handtracking.distribution.package.source_files',return_value={'README.md':source}):build(archive)
            with zipfile.ZipFile(archive) as z:m=json.loads(z.read(MANIFEST))
            m['mode']='recovered'
            with zipfile.ZipFile(archive,'w') as z:
                z.writestr(MANIFEST,json.dumps(m));z.writestr('README.md','source')
            with self.assertRaises(ValueError):verify(archive)
            with self.assertRaises(ValueError):build(root/'missing.zip',root/'absent')

    def test_original_catalog_scope(self):
        expected=expected_originals()
        self.assertEqual(sum(r['kind']=='original_model' for r in expected.values()),21)
        self.assertEqual(sum(r['kind']=='decoded_original_model' for r in expected.values()),10)
        self.assertEqual(len(expected),51)
