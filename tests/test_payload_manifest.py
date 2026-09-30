import base64
import hashlib
import io
import struct
import unittest
from tools.payload_manifest import inspect_payload, fields, MAX_MANIFEST


def varint(n):
    out = bytearray()
    while n > 127:
        out.append((n & 127) | 128)
        n >>= 7
    out.append(n)
    return bytes(out)


def integer(field, n):
    return varint(field << 3) + varint(n)


def message(field, data):
    return varint((field << 3) | 2) + varint(len(data)) + data


def fixture(kind=0, minor=0, name=b'system', extent_blocks=1, offset=0):
    extent = integer(1, 0) + integer(2, extent_blocks)
    operation = integer(1, kind) + integer(2, offset) + integer(3, 4) + message(6, extent)
    new = integer(1, 4096) + message(2, b'x' * 32)
    part = message(1, name) + message(7, new) + message(8, operation)
    manifest = integer(12, minor) + message(13, part)
    metadata = struct.pack('>4sQQI', b'CrAU', 2, len(manifest), 0) + manifest
    payload = metadata + b'data'
    properties = {'METADATA_SIZE': str(len(metadata)), 'FILE_SIZE': str(len(payload)),
                  'METADATA_HASH': base64.b64encode(hashlib.sha256(metadata).digest()).decode()}
    return io.BytesIO(payload), len(payload), properties


class PayloadTests(unittest.TestCase):
    def test_full_manifest_not_boot_claim(self):
        stream, size, properties = fixture()
        report = inspect_payload(stream, size, properties)
        self.assertEqual(report['payload_kind_declared'], 'FULL')
        self.assertFalse(report['reconstruction_verified'])
        self.assertEqual(report['stable_channel'], 'UNVERIFIED')
        self.assertEqual(report['partitions'][0]['operation_counts'], {'REPLACE': 1})
        self.assertEqual(stream.read(), b'data')  # No operation data read.

    def test_delta(self):
        report = inspect_payload(*fixture(kind=4, minor=2))
        self.assertEqual(report['payload_kind_declared'], 'DELTA')
        self.assertTrue(report['partitions'][0]['source_dependency_declared'])

    def test_unknown_operation_not_silently_supported(self):
        report = inspect_payload(*fixture(kind=999))
        self.assertTrue(report['partitions'][0]['unknown_operations'])

    def test_invalid_ranges_and_names(self):
        for kwargs in ({'offset': 9999}, {'extent_blocks': 2}, {'name': b'../system'}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                inspect_payload(*fixture(**kwargs))

    def test_metadata_hash(self):
        stream, size, properties = fixture()
        properties['METADATA_HASH'] = base64.b64encode(b'0' * 32).decode()
        with self.assertRaisesRegex(ValueError, 'HASH mismatch'):
            inspect_payload(stream, size, properties)

    def test_truncated_metadata(self):
        with self.assertRaisesRegex(ValueError, 'Truncated'):
            inspect_payload(io.BytesIO(b'CrAU'), 4, {})

    def test_manifest_limit_before_allocation(self):
        header = struct.pack('>4sQQI', b'CrAU', 2, MAX_MANIFEST + 1, 0)
        with self.assertRaisesRegex(ValueError, 'limits'):
            inspect_payload(io.BytesIO(header), MAX_MANIFEST * 2, {})

    def test_bad_wire_encoding(self):
        for data in (b'\0', b'\x08\x80', b'\x0a\x10a', b'\x0b', b'\xff' * 11):
            with self.subTest(data=data), self.assertRaises(ValueError):
                fields(data)

    def test_duplicate_singular(self):
        from tools.payload_manifest import one
        with self.assertRaises(ValueError):
            one(fields(integer(1, 2) + integer(1, 3)), 1, 0)
