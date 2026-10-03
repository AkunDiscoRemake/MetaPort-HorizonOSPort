import hashlib
import struct
import unittest
import zlib
from horizon.ui.dex_contract import Dex

# Minimal synthetic standard DEX subset, not a runnable application/complete map.
def fixture(native=True, descriptor_return='J'):
    strings=['Lcom/oculus/vrshell/ShellApplication;','nativeInit',descriptor_return]
    b=bytearray(184);b[:8]=b'dex\n039\0'
    struct.pack_into('<II',b,36,112,0x12345678)
    for at,count,offset in [(56,3,112),(64,2,124),(72,1,132),(88,1,144),(96,1,152)]:
        struct.pack_into('<II',b,at,count,offset)
    struct.pack_into('<II',b,124,0,2)
    struct.pack_into('<III',b,132,2,1,0)
    struct.pack_into('<HHI',b,144,0,0,1)
    for i,s in enumerate(strings):
        struct.pack_into('<I',b,112+4*i,len(b));b.extend(bytes([len(s)])+s.encode()+b'\0')
    struct.pack_into('<I',b,176,len(b))
    b.extend(b'\0\0\1\0\0'+(b'\x89\2' if native else b'\x09')+b'\0')
    struct.pack_into('<I',b,32,len(b));return seal(b)

def seal(b):
    b[12:32]=hashlib.sha1(b[32:]).digest()
    struct.pack_into('<I',b,8,zlib.adler32(b[12:])&0xffffffff)
    return bytes(b)

class DexContractTests(unittest.TestCase):
    def test_reads_definition_not_just_reference(self):
        methods=Dex(fixture()).native_methods('Lcom/oculus/vrshell/ShellApplication;')
        self.assertEqual(methods[0]['descriptor'],'()J')
        self.assertTrue(methods[0]['static'])
        self.assertEqual(Dex(fixture(False)).native_methods('Lcom/oculus/vrshell/ShellApplication;'),[])
        self.assertEqual(Dex(fixture()).native_methods('Lother;'),[])
    def test_checksum_and_extent_fail_closed(self):
        b=bytearray(fixture());b[-1]^=1
        with self.assertRaises(ValueError):Dex(b)
        b=bytearray(fixture());struct.pack_into('<I',b,60,len(b)+4)
        with self.assertRaises(ValueError):Dex(seal(b))
    def test_native_code_and_uleb_rejected(self):
        b=bytearray(fixture());b[-1]=1
        with self.assertRaises(ValueError):Dex(seal(b)).native_methods('Lcom/oculus/vrshell/ShellApplication;')
        d=Dex(fixture())
        with self.assertRaises(ValueError):d.uleb(len(d.data))
    def test_unsupported_magic(self):
        with self.assertRaises(ValueError):Dex(b'cdex001\0'+bytes(200))
