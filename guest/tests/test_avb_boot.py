import hashlib
from pathlib import Path
import struct
import tempfile
import unittest
from guest.avb_boot import read_vbmeta,parameters


def vbmeta(chain=None):
    aux=b''
    if chain:
        name=chain.encode();length=(76+len(name)+7)//8*8
        aux=struct.pack('>QQIIII60s',4,length,0,len(name),0,0,bytes(60))+name
        aux=aux.ljust(16+length,b'\0')
    h=bytearray(256);h[:4]=b'AVB0'
    struct.pack_into('>QQ',h,12,0,len(aux));struct.pack_into('>QQ',h,96,0,len(aux))
    return bytes(h)+aux


class AvbBootTests(unittest.TestCase):
    def test_chain_digest_excludes_padding(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp);a=vbmeta('vbmeta_system');b=vbmeta()
            (p/'vbmeta.img').write_bytes(a+bytes(100))
            (p/'vbmeta_system.img').write_bytes(b+bytes(100))
            r=parameters(p)
            self.assertEqual(r['size'],len(a+b));self.assertEqual(r['digest'],hashlib.sha256(a+b).hexdigest())
            self.assertFalse(r['trust_anchor_verified']);self.assertFalse(r['verification_disabled'])

    def test_reject_cycles_and_disabled_verification(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'vbmeta.img';p.write_bytes(vbmeta('vbmeta'))
            with self.assertRaises(ValueError):parameters(p.parent)
            b=bytearray(vbmeta());struct.pack_into('>I',b,120,2);p.write_bytes(b)
            with self.assertRaises(ValueError):read_vbmeta(p)

    def test_footer_bounds(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'system.img';footer=bytearray(64);footer[:4]=b'AVBf'
            struct.pack_into('>QQ',footer,20,4096,256)
            p.write_bytes(bytes(4096)+vbmeta()+footer)
            self.assertEqual(read_vbmeta(p)[0],vbmeta())
            struct.pack_into('>Q',footer,20,999999);p.write_bytes(bytes(4096)+vbmeta()+footer)
            with self.assertRaises(ValueError):read_vbmeta(p)
