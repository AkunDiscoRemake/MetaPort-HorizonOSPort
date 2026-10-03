import bz2
import hashlib
import io
import lzma
from pathlib import Path
import tempfile
import unittest
from tools.payload_manifest import fields
from tools.reconstruct_ota import decode_operation, reconstruct_partition
from test_payload_manifest import integer, message


class ReconstructionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.out = Path(self.tmp.name) / 'system.img'

    def fixture(self, kind=8, checksum=None, start=0, extra=b''):
        data = b'example fixture'.ljust(4096, b'\0')
        blob = lzma.compress(data) if kind == 8 else bz2.compress(data) if kind == 1 else data
        extent = integer(1, start) + integer(2, 1)
        op = integer(1, kind) + integer(3, len(blob)) + message(6, extent)
        op += message(8, checksum or hashlib.sha256(blob).digest())
        new = integer(1, 4096) + message(2, hashlib.sha256(data).digest())
        part = fields(message(1, b'system') + message(7, new) + message(8, op) + extra)
        return blob, part, data

    def test_all_supported_compressions(self):
        for kind in (0, 1, 8):
            blob, part, expected = self.fixture(kind)
            result = reconstruct_partition(io.BytesIO(blob), 0, len(blob), part, 4096, self.out)
            self.assertTrue(result['sha256_match'])
            self.assertEqual(self.out.read_bytes(), expected)
            self.out.unlink()

    def test_wrong_operation_hash_removes_partial(self):
        blob, part, _ = self.fixture(checksum=b'x' * 32)
        with self.assertRaisesRegex(ValueError, 'Operation SHA'):
            reconstruct_partition(io.BytesIO(blob), 0, len(blob), part, 4096, self.out)
        self.assertEqual(list(self.out.parent.iterdir()), [])

    def test_wrong_final_hash(self):
        blob, part, _ = self.fixture()
        part[7] = [(2, integer(1, 4096) + message(2, b'x' * 32))]
        with self.assertRaisesRegex(ValueError, 'partition SHA'):
            reconstruct_partition(io.BytesIO(blob), 0, len(blob), part, 4096, self.out)
        self.assertFalse(self.out.exists())

    def test_overlap(self):
        blob, part, _ = self.fixture()
        part[8] *= 2
        with self.assertRaisesRegex(ValueError, 'overlap'):
            reconstruct_partition(io.BytesIO(blob), 0, len(blob), part, 4096, self.out)

    def test_no_overwrite(self):
        blob, part, _ = self.fixture()
        self.out.write_bytes(b'keep')
        with self.assertRaisesRegex(ValueError, 'overwrite'):
            reconstruct_partition(io.BytesIO(blob), 0, len(blob), part, 4096, self.out)
        self.assertEqual(self.out.read_bytes(), b'keep')

    def test_delta_rejected(self):
        blob, part, _ = self.fixture(extra=message(6, b''))
        with self.assertRaisesRegex(ValueError, 'Delta'):
            reconstruct_partition(io.BytesIO(blob), 0, len(blob), part, 4096, self.out)

    def test_bombs_and_trailing_compressed_data(self):
        for kind, compress in ((1, bz2.compress), (8, lzma.compress)):
            for blob in (compress(b'a' * 10000), compress(b'a') + b'trailing'):
                with self.assertRaises(ValueError):
                    decode_operation(kind, blob, 4096)

    def test_unknown_operation(self):
        with self.assertRaisesRegex(ValueError, 'Unsupported'):
            decode_operation(4, b'x', 4096)

    def test_all_partition_selection_with_local_fixture(self):
        import struct
        import zipfile
        from unittest.mock import patch
        from tools.reconstruct_ota import reconstruct
        blob, part, data = self.fixture(kind=0)
        # Re-encode two independent partitions, with the second operation offset adjusted.
        new = integer(1, 4096) + message(2, hashlib.sha256(data).digest())
        manifest = b''
        for index,name in enumerate((b'boot',b'system')):
            extent=integer(1,0)+integer(2,1)
            operation=(integer(1,0)+integer(2,index*len(blob))+integer(3,len(blob))+
                       message(6,extent)+message(8,hashlib.sha256(blob).digest()))
            manifest+=message(13,message(1,name)+message(7,new)+message(8,operation))
        payload=struct.pack('>4sQQI',b'CrAU',2,len(manifest),0)+manifest+blob+blob
        archive=self.out.parent/'ota.zip'
        with zipfile.ZipFile(archive,'w') as z: z.writestr('payload.bin',payload)
        validated={'sha256':'fixture', 'payload_manifest':{'payload_minor':0,'partial_update_declared':False,
                   'block_size':4096,'partitions':[{'name':n,'new_size_bytes':4096} for n in ('boot','system')]}}
        with patch('tools.reconstruct_ota.inspect',return_value=validated):
            r=reconstruct(archive,self.out.parent/'images',selected=None)
        self.assertEqual(set(r['partitions']),{'boot','system'})
        self.assertTrue(all(p['sha256_match'] for p in r['partitions'].values()))
