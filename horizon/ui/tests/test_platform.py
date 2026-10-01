import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from horizon.ui.inspect_platform import verify_partition, TARGETS

class PlatformTests(unittest.TestCase):
    def test_hash_and_size_required(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'image';p.write_bytes(b'fixture')
            expected={'size_bytes':7,'sha256_match':True,'sha256':hashlib.sha256(b'fixture').hexdigest()}
            verify_partition(p,expected)
            for key,value in [('size_bytes',8),('sha256_match',False),('sha256','wrong')]:
                with self.assertRaises(ValueError):verify_partition(p,{**expected,key:value})
    def test_targets_are_unique_arm64_inventory_entries(self):
        inv=json.loads(Path('analysis/builds/52168470052900520/static-analysis.json').read_text())['partitions']
        for partition,paths in TARGETS.items():
            for path in paths:
                self.assertIn('/lib64/',path)
                self.assertEqual(len([e for e in inv[partition]['entries'] if e['kind']=='file' and e['path']==path]),1)
