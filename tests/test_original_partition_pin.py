# SPDX-License-Identifier: GPL-3.0-only
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from horizon.ui.prepare_shell_apk import verify_partition

class PartitionPin(unittest.TestCase):
    def test_self_consistent_forged_manifest_is_not_provenance(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);image=root/'system.img';image.write_bytes(b'original')
            record={'sha256_match':True,'size_bytes':8,'sha256':hashlib.sha256(b'original').hexdigest()}
            recon={'source_zip_sha256':'ota','partitions':{'system':record}}
            pinned=root/'pinned.json';pinned.write_text(json.dumps(recon))
            with patch('horizon.ui.prepare_shell_apk.RECONSTRUCTION',pinned):
                verify_partition(root,'system',recon,{'ota_sha256':'ota'})
                image.write_bytes(b'modified');record['sha256']=hashlib.sha256(b'modified').hexdigest()
                with self.assertRaises(ValueError):verify_partition(root,'system',recon,{'ota_sha256':'ota'})
                image.write_bytes(b'original');record['sha256']=hashlib.sha256(b'original').hexdigest()
                for value in (False,'true'):
                    record['sha256_match']=value
                    with self.assertRaises(ValueError):verify_partition(root,'system',recon,{'ota_sha256':'ota'})
                record['sha256_match']=True
                with self.assertRaises(ValueError):verify_partition(root,'system',recon,{'ota_sha256':'wrong'})
