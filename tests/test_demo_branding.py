# SPDX-License-Identifier: GPL-3.0-only
import hashlib
import json
from pathlib import Path
import struct
import unittest
import xml.etree.ElementTree as ET

ROOT=Path(__file__).resolve().parents[1]/'port/branding'

class DemoBranding(unittest.TestCase):
    def test_origin_resources_and_requested_name(self):
        record=json.loads((ROOT/'branding.json').read_text())
        sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
        self.assertEqual(sha(ROOT/'metaport-icon-original.png'),record['original_sha256'])
        for name,digest in record['generated_files'].items():
            path=ROOT/name;self.assertEqual(sha(path),digest)
            if path.suffix=='.xml':ET.parse(path)
        values=ET.parse(ROOT/'android-res/values/metaport_demo_branding.xml')
        self.assertEqual(values.find('string').text,'MetaPort official demo by ahambolota')
        self.assertFalse(record['applied_to_original_apk'])
        self.assertFalse(record['functional_demo_validated'])

    def test_launcher_density_dimensions(self):
        for density,size in (('mdpi',48),('hdpi',72),('xhdpi',96),('xxhdpi',144),('xxxhdpi',192)):
            data=(ROOT/f'android-res/mipmap-{density}/ic_metaport_demo.png').read_bytes()
            self.assertEqual(data[:8],b'\x89PNG\r\n\x1a\n')
            self.assertEqual(struct.unpack('>II',data[16:24]),(size,size))
