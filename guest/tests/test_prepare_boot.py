import gzip
import hashlib
from pathlib import Path
import struct
import tempfile
import unittest
from guest.prepare_boot import prepare
from guest.tests.test_ramdisk import record


class PrepareTests(unittest.TestCase):
    def test_original_bytes_and_vendor_first_order(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); images=root/'images';images.mkdir()
            generic=gzip.compress(record('init',b'fixture-not-an-executable')+record('TRAILER!!!'))
            vendor=gzip.compress(record('fstab.fixture',b'fixture')+record('TRAILER!!!'))
            boot=bytearray(4096);boot[:8]=b'ANDROID!'
            struct.pack_into('<IIII',boot,8,0,len(generic),0,1584)
            struct.pack_into('<I',boot,40,4)
            (images/'boot.img').write_bytes(boot+generic)
            header=bytearray(4096);header[:8]=b'VNDRBOOT'
            struct.pack_into('<II',header,8,4,4096)
            struct.pack_into('<I',header,24,len(vendor))
            struct.pack_into('<I',header,2096,2128)
            (images/'vendor_boot.img').write_bytes(header+vendor+bytes((-len(vendor))%4096))
            result=prepare(images,root/'output')
            self.assertEqual((root/'output/original-initrd').read_bytes(),vendor+generic)
            self.assertEqual(result['combined_initrd_sha256'],hashlib.sha256(vendor+generic).hexdigest())
            self.assertFalse(result['vendor_bootconfig_appended'])
            self.assertFalse(result['original_ramdisks']['boot']['inventory']['executed'])
