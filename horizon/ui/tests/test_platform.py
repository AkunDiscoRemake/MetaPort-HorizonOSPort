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
    def test_internal_targets_are_observed_callees_of_same_pinned_library(self):
        root=Path('analysis/builds/52168470052900520')
        policy=json.loads(Path('horizon/ui/platform-native-policy.json').read_text())
        for lib in policy['libraries']:
            report=json.loads((root/('shell-'+lib['prefix']+'-native.json')).read_text())
            self.assertEqual(report['program_sha256'].lower(),lib['sha256'])
            base=int(report['image_base'],16)
            callees={(c['name'],int(c['ghidra_address'],16)-base)
                     for f in report['functions'] for c in f.get('direct_callees',[]) if not c['external']}
            for helper in lib['internal_call_targets']:
                self.assertIn((helper['name'],helper['elf_address']),callees)
