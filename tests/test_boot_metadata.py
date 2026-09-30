import gzip
from pathlib import Path
import struct
import tempfile
import unittest
from tools.boot_metadata import inspect_image, bounded_gzip, kernel_identity


class BootTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / 'boot.img'

    def test_v4_boot_and_embedded_config(self):
        kernel = bytearray(64)
        kernel[56:60] = b'ARM\x64'
        kernel += b'Linux version fixture-only\0'
        kernel += b'IKCFG_ST' + gzip.compress(b'CONFIG_ARCH_QCOM=y\n# CONFIG_VIRTIO is not set\nUNRELATED=x\n') + b'IKCFG_ED'
        packed = gzip.compress(kernel)
        header = bytearray(4096)
        header[:8] = b'ANDROID!'
        struct.pack_into('<IIII', header, 8, len(packed), 0, 0, 1584)
        struct.pack_into('<I', header, 40, 4)
        self.path.write_bytes(header + packed + bytes(4096-len(packed)))
        r = inspect_image(self.path)
        self.assertEqual(r['kernel']['linux_version_banner'], 'Linux version fixture-only')
        self.assertEqual(r['kernel']['selected_config'], {'CONFIG_ARCH_QCOM':'y', 'CONFIG_VIRTIO':'not set'})
        self.assertFalse(r['boot_tested'])

    def test_vendor_boot_v4(self):
        data=bytearray(4096)
        data[:8]=b'VNDRBOOT'
        struct.pack_into('<II',data,8,4,4096)
        struct.pack_into('<I',data,2096,2128)
        self.path.write_bytes(data)
        r=inspect_image(self.path)
        self.assertEqual(r['ramdisk_fragment_count'],0)
        self.assertEqual(r['image_format'],'VENDOR_BOOT')

    def test_reject_out_of_bounds_boot(self):
        data=bytearray(4096)
        data[:8]=b'ANDROID!'
        struct.pack_into('<IIII',data,8,8192,0,0,1584)
        struct.pack_into('<I',data,40,4)
        self.path.write_bytes(data)
        with self.assertRaises(ValueError): inspect_image(self.path)

    def test_old_version_not_misparsed(self):
        data=bytearray(4096);data[:8]=b'ANDROID!'
        self.path.write_bytes(data)
        self.assertEqual(inspect_image(self.path)['status'],'UNSUPPORTED_HEADER_VERSION')

    def test_gzip_limits(self):
        for data in (gzip.compress(b'x'*2000),b'not gzip'):
            with self.assertRaises(ValueError): bounded_gzip(data,100)

    def test_unknown_kernel_not_bootable_claim(self):
        self.assertEqual(kernel_identity(b'unknown')['status'],'UNSUPPORTED_KERNEL_ENCODING')

    def test_elf_identity(self):
        data=bytearray(64);data[:6]=b'\x7fELF\x02\x01';struct.pack_into('<H',data,18,183)
        self.path.write_bytes(data)
        self.assertEqual(inspect_image(self.path)['machine'],183)
        self.assertFalse(inspect_image(self.path)['boot_tested'])
