import gzip
import struct
import unittest
from guest.ramdisk import inventory


def record(name,data=b'',mode=0o100644,magic=b'070701',checksum=0):
    name=name.encode()+b'\0'
    fields=[1,mode,0,0,1,0,len(data),0,0,0,0,len(name),checksum]
    out=magic+b''.join(f'{v:08x}'.encode() for v in fields)+name
    out+=b'\0'*((-len(out))%4)
    out+=data
    out+=b'\0'*((-len(out))%4)
    return out


class RamdiskTests(unittest.TestCase):
    def test_real_newc_structure_and_gzip(self):
        blob=record('first_stage_ramdisk/fstab.eureka',b'/dev/block/real /system ext4 ro wait\n')+record('TRAILER!!!')
        report=inventory(gzip.compress(blob))
        self.assertFalse(report['executed'])
        self.assertEqual(report['configuration'][0]['path'],'first_stage_ramdisk/fstab.eureka')
        self.assertEqual(report['entries'][0]['size_bytes'],len(b'/dev/block/real /system ext4 ro wait\n'))

    def test_paths_never_extracted(self):
        for name in ('../escape','/absolute'):
            with self.assertRaises(ValueError): inventory(record(name)+record('TRAILER!!!'))

    def test_trailer_required(self):
        with self.assertRaises(ValueError): inventory(record('file'))

    def test_truncation(self):
        with self.assertRaises(ValueError): inventory(record('file',b'hello')[:-7])

    def test_crc_checked(self):
        good=record('file',b'ab',magic=b'070702',checksum=195)+record('TRAILER!!!')
        self.assertEqual(inventory(good)['entries'][0]['size_bytes'],2)
        with self.assertRaises(ValueError): inventory(good.replace(b'000000c3',b'00000000'))

    def test_concatenated_archives(self):
        blob=record('a')+record('TRAILER!!!')+bytes(512)+record('b')+record('TRAILER!!!')
        self.assertEqual(inventory(blob)['archive_trailers'],2)

    def test_each_concatenated_archive_requires_trailer(self):
        with self.assertRaises(ValueError):
            inventory(record('a')+record('TRAILER!!!')+record('b'))

    def test_lz4_legacy(self):
        try: import lz4.block
        except ImportError: self.skipTest('Optional lz4 package not installed')
        raw=record('file',b'fixture')+record('TRAILER!!!')
        block=lz4.block.compress(raw,store_size=False)
        blob=b'\x02\x21\x4c\x18'+struct.pack('<I',len(block))+block
        self.assertEqual(inventory(blob)['compression'],'lz4-legacy')
