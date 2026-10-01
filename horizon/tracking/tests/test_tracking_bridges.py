# SPDX-License-Identifier: GPL-3.0-only
import hashlib
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from horizon.tracking.prepare_tracking_bridges import prepare_bridges

class BridgePreparation(unittest.TestCase):
    def test_pinned_bytes_and_missing_inventory(self):
        blob=b'fixture bridge';sha=hashlib.sha256(blob).hexdigest()
        spec=(('bridge.so','hand-test',len(blob),sha),)
        inventory=[{'path':'/lib64/bridge.so','kind':'file'}]
        def dump(image,entry,target): target.write_bytes(blob)
        with tempfile.TemporaryDirectory() as temp, patch('horizon.tracking.prepare_tracking_bridges.BRIDGES',spec), patch('horizon.tracking.prepare_tracking_bridges.dump_entry',side_effect=dump):
            r=prepare_bridges(Path('verified-image'),inventory,temp)
            self.assertEqual(r['modules'][0]['sha256'],sha)
            self.assertFalse(r['firmware_executed']);self.assertFalse(r['private_abi_validated'])
            with self.assertRaises(ValueError):prepare_bridges(Path('verified-image'),[],temp)
            with self.assertRaises(ValueError):prepare_bridges(Path('verified-image'),inventory*2,temp)

    def test_wrong_size_or_hash_rejected(self):
        inventory=[{'path':'/lib64/bridge.so','kind':'file'}]
        for size,sha in ((99,hashlib.sha256(b'abc').hexdigest()),(3,'0'*64)):
            with tempfile.TemporaryDirectory() as temp, patch('horizon.tracking.prepare_tracking_bridges.BRIDGES',(('bridge.so','hand-test',size,sha),)), patch('horizon.tracking.prepare_tracking_bridges.dump_entry',side_effect=lambda image,entry,target:target.write_bytes(b'abc')):
                with self.assertRaises(ValueError):prepare_bridges(Path('verified-image'),inventory,temp)
