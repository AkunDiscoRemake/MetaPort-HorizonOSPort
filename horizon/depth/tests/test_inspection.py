import json
from pathlib import Path
import tempfile
import unittest
from horizon.depth.inspect_models import inspect, OTA_SHA256, RESOURCES

class DepthInspectionTests(unittest.TestCase):
    def test_rejects_wrong_ota_before_extraction(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d);r=p/'reconstruction.json'
            r.write_text(json.dumps({'source_zip_sha256':'wrong'}))
            with self.assertRaisesRegex(ValueError,'Wrong OTA'):
                inspect(p,r,p/'report.json')
            self.assertFalse((p/'report.json').exists())
    def test_rejects_unverified_partition(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d);r=p/'reconstruction.json'
            r.write_text(json.dumps({'source_zip_sha256':OTA_SHA256,
                'partitions':{'system':{'sha256_match':False}}}))
            with self.assertRaisesRegex(ValueError,'Wrong partition'):
                inspect(p,r,p/'report.json')
            self.assertFalse((p/'report.json').exists())
    def test_resources_match_firmware_inventory(self):
        inv=json.loads(Path('analysis/builds/52168470052900520/static-analysis.json').read_text())['partitions']
        for part,paths in RESOURCES.items():
            for path in paths:
                rows=[e for e in inv[part]['entries'] if e['path']==path and e['kind']=='file']
                self.assertEqual(len(rows),1)
                self.assertLess(rows[0]['size_bytes'],128*1024*1024)
