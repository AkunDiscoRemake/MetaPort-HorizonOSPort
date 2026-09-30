import struct
import unittest
import zlib
from horizon.tracking.ptez import inspect_container, pte_header, MAX_OUTPUT


def model():
    return struct.pack('<I4sHHH2xiI',16,b'ET12',6,8,4,8,1)+b'XnnpackBackend\0'


def container(raw=None,offset=128,wbits=15):
    raw=model() if raw is None else raw
    c=zlib.compressobj(wbits=wbits)
    return struct.pack('<4sIQ8s',b'etz0',24,len(raw),b'deflate\0')+bytes(offset-24)+c.compress(raw)+c.flush()


class PtezTests(unittest.TestCase):
    def test_bounded_zlib_and_raw_deflate(self):
        for wbits in (15,-15):
            report,raw=inspect_container(container(wbits=wbits))
            self.assertEqual(raw,model())
            self.assertEqual(report['payload_offset'],128)
            self.assertEqual(report['zlib_wbits'],wbits)
            self.assertFalse(report['inference_tested'])

    def test_truncation_trailing_data_and_bad_size_rejected(self):
        blob=container()
        cases=[blob[:-1],blob+b'garbage',blob[:8]+struct.pack('<Q',len(model())-1)+blob[16:]]
        for bad in cases:
            report,raw=inspect_container(bad)
            self.assertIsNone(raw)
            self.assertEqual(report['status'],'NO_UNIQUE_VALIDATED_STREAM')

    def test_limits_and_header(self):
        blob=container()
        for bad in [b'',b'bad!'+blob[4:],blob[:8]+struct.pack('<Q',MAX_OUTPUT+1)+blob[16:],blob[:16]+b'unknown\0'+blob[24:]]:
            with self.assertRaises(ValueError): inspect_container(bad)

    def test_deflate_bomb_stops_at_declared_limit(self):
        blob=container(b'X'*1000000)
        blob=blob[:8]+struct.pack('<Q',32)+blob[16:]
        report,raw=inspect_container(blob)
        self.assertIsNone(raw)

    def test_root_vtable_bounds(self):
        raw=model()
        for bad in [raw[:4]+b'NOPE'+raw[8:],struct.pack('<I',999999)+raw[4:],raw[:16]+struct.pack('<i',999999)+raw[20:],raw[:12]+struct.pack('<H',8)+raw[14:]]:
            with self.assertRaises(ValueError): pte_header(bad)
