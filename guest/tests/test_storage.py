import hashlib
import struct
import unittest
import zlib
from guest.storage import lp_metadata,gpt,MIB,META_MAX,physical_layout


class StorageTests(unittest.TestCase):
    def test_lp_geometry_and_table_checksums(self):
        prefix,layout,size=lp_metadata({'system':4096,'vendor':8192})
        geo=bytearray(prefix[4096:4096+52]);digest=bytes(geo[8:40]);geo[8:40]=bytes(32)
        self.assertEqual(hashlib.sha256(geo).digest(),digest)
        self.assertEqual(prefix[4096:8192],prefix[8192:12288])
        h=bytearray(prefix[12288:12416]);digest=bytes(h[12:44]);h[12:44]=bytes(32)
        self.assertEqual(hashlib.sha256(h).digest(),digest)
        n=struct.unpack_from('<I',h,44)[0]
        self.assertEqual(hashlib.sha256(prefix[12416:12416+n]).digest(),h[48:80])
        for slot in range(4):
            self.assertEqual(prefix[12288:12288+META_MAX],prefix[12288+slot*META_MAX:12288+(slot+1)*META_MAX])
        self.assertEqual(layout[0]['offset'],MIB)
        self.assertGreaterEqual(size,layout[-1]['offset']+layout[-1]['size_bytes'])

    def test_gpt_crc_and_backup(self):
        chunks,layout,total=gpt({'super':4*MIB,'metadata':MIB})
        data=dict(chunks);header=bytearray(data[512][:92]);crc=struct.unpack_from('<I',header,16)[0]
        struct.pack_into('<I',header,16,0)
        self.assertEqual(zlib.crc32(header),crc)
        self.assertEqual(zlib.crc32(data[1024]),struct.unpack_from('<I',header,88)[0])
        self.assertEqual(data[1024],data[total-33*512])
        self.assertEqual(data[0][510:],b'\x55\xaa')
        self.assertLess(layout[-1]['offset']+layout[-1]['size_bytes'],total-33*512)

    def test_reject_unbounded_or_unaligned(self):
        for sizes in ({'system':1},{'../escape':4096},{'system':9*1024*MIB},{}):
            with self.assertRaises(ValueError):lp_metadata(sizes)

    def test_userdata_appended_without_moving_existing_roles(self):
        evidence={name:{'size_bytes':4096} for name in ('boot','vbmeta','vbmeta_system')}
        old=physical_layout(evidence,4*MIB)
        new=physical_layout(evidence,4*MIB,1024)
        self.assertNotIn('userdata',old)
        self.assertEqual(new['userdata'],1024*MIB)
        _,before,_=gpt(old);chunks,after,total=gpt(new)
        self.assertEqual(before,after[:-1])
        self.assertEqual(after[-1]['name'],'userdata')
        self.assertEqual(after[-1]['offset']%MIB,0)
        self.assertLess(after[-1]['offset']+after[-1]['size_bytes'],total-33*512)
        self.assertEqual(dict(chunks)[1024],dict(chunks)[total-33*512])

    def test_userdata_limits(self):
        evidence={name:{'size_bytes':4096} for name in ('boot','vbmeta','vbmeta_system')}
        for size in (-1,1,127,1025,True,128.0,'128'):
            with self.assertRaises(ValueError):physical_layout(evidence,4*MIB,size)
        self.assertEqual(physical_layout(evidence,4*MIB,128)['userdata'],128*MIB)
