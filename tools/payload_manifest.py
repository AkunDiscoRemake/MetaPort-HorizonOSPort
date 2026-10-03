"""Bounded read-only AOSP payload v2 manifest inspection, not an extractor.

Wire field mapping: AOSP system/update_engine/update_metadata.proto,
blob 6d16da40e53720078b2e4f3689dbb296eb325bee. Unknown fields are not interpreted.
"""
import base64
from collections import Counter
import hashlib
import re
import struct

MAX_MANIFEST = 16 * 1024 * 1024
MAX_FIELDS = 250000
OPERATIONS = {0: 'REPLACE', 1: 'REPLACE_BZ', 2: 'MOVE', 3: 'BSDIFF',
              4: 'SOURCE_COPY', 5: 'SOURCE_BSDIFF', 6: 'ZERO', 7: 'DISCARD',
              8: 'REPLACE_XZ', 9: 'PUFFDIFF', 10: 'BROTLI_BSDIFF',
              11: 'ZUCCHINI', 12: 'LZ4DIFF_BSDIFF', 13: 'LZ4DIFF_PUFFDIFF'}
SOURCE_OPERATIONS = {2, 3, 4, 5, 9, 10, 11, 12, 13}


def varint(data, offset):
    value = 0
    for shift in range(0, 70, 7):
        if offset >= len(data):
            raise ValueError('Truncated varint')
        byte = data[offset]
        offset += 1
        if shift == 63 and byte > 1:
            raise ValueError('Varint overflow')
        value |= (byte & 127) << shift
        if not byte & 128:
            return value, offset
    raise ValueError('Varint overflow')


def fields(data):
    if len(data) > MAX_MANIFEST:
        raise ValueError('Protobuf exceeds limit')
    result = {}
    offset = count = 0
    while offset < len(data):
        count += 1
        if count > MAX_FIELDS:
            raise ValueError('Too many protobuf fields')
        tag, offset = varint(data, offset)
        number, wire = tag >> 3, tag & 7
        if not 0 < number < (1 << 29):
            raise ValueError('Invalid field number')
        if wire == 0:
            value, offset = varint(data, offset)
        elif wire in (1, 2, 5):
            if wire == 2:
                size, offset = varint(data, offset)
            else:
                size = 8 if wire == 1 else 4
            if size > len(data) - offset:
                raise ValueError('Truncated protobuf field')
            value = data[offset:offset + size]
            offset += size
        else:
            raise ValueError('Unsupported protobuf wire type')
        result.setdefault(number, []).append((wire, value))
    return result


def one(message, number, wire, default=None):
    values = message.get(number, [])
    if not values:
        return default
    if len(values) != 1 or values[0][0] != wire:
        raise ValueError('Duplicate singular field or wrong wire type')
    return values[0][1]


def repeated(message, number):
    for wire, value in message.get(number, []):
        if wire != 2:
            raise ValueError('Wrong message wire type')
        yield fields(value)


def read_exact(stream, count):
    data = stream.read(count)
    if len(data) != count:
        raise ValueError('Truncated payload metadata')
    return data


def inspect_payload(stream, payload_size, properties):
    header = read_exact(stream, 24)
    magic, major, manifest_size, signature_size = struct.unpack('>4sQQI', header)
    if magic != b'CrAU' or major != 2:
        raise ValueError('Only CrAU payload major version 2 is supported')
    if not 0 < manifest_size <= MAX_MANIFEST or signature_size > MAX_MANIFEST:
        raise ValueError('Payload metadata exceeds limits')
    data_start = 24 + manifest_size + signature_size
    if data_start > payload_size:
        raise ValueError('Metadata exceeds payload size')
    manifest_bytes = read_exact(stream, manifest_size)
    metadata = header + manifest_bytes
    if int(properties['METADATA_SIZE']) != len(metadata):
        raise ValueError('METADATA_SIZE mismatch')
    if int(properties['FILE_SIZE']) != payload_size:
        raise ValueError('FILE_SIZE mismatch')
    if hashlib.sha256(metadata).digest() != base64.b64decode(properties['METADATA_HASH'], validate=True):
        raise ValueError('METADATA_HASH mismatch')
    manifest = fields(manifest_bytes)
    block_size = one(manifest, 3, 0, 4096)
    if block_size == 0 or block_size > 1024 * 1024 or block_size & (block_size - 1):
        raise ValueError('Invalid block size')
    minor = one(manifest, 12, 0, 0)
    partial = one(manifest, 16, 0, 0)
    if partial not in (0, 1):
        raise ValueError('Invalid partial_update flag')
    partitions = []
    seen = set()
    for part in repeated(manifest, 13):
        raw_name = one(part, 1, 2)
        if raw_name is None:
            raise ValueError('Missing partition name')
        name = raw_name.decode('utf-8')
        if not re.fullmatch(r'[A-Za-z0-9_-]{1,100}', name) or name in seen:
            raise ValueError('Invalid or duplicate partition name')
        seen.add(name)
        new = fields(one(part, 7, 2, b''))
        size = one(new, 1, 0)
        new_hash = one(new, 2, 2, b'')
        if new_hash and len(new_hash) != 32:
            raise ValueError('Invalid partition SHA-256 length')
        counts = Counter()
        requires_source = one(part, 6, 2) is not None
        unknown = False
        for operation in repeated(part, 8):
            kind = one(operation, 1, 0)
            if kind is None:
                raise ValueError('Missing operation type')
            counts[OPERATIONS.get(kind, 'UNKNOWN_' + str(kind))] += 1
            unknown |= kind not in OPERATIONS
            requires_source |= kind in SOURCE_OPERATIONS or bool(operation.get(4))
            offset = one(operation, 2, 0, 0)
            length = one(operation, 3, 0, 0)
            if offset + length > payload_size - data_start:
                raise ValueError('Operation data range exceeds payload')
            for extent in repeated(operation, 6):
                start = one(extent, 1, 0)
                blocks = one(extent, 2, 0)
                if start is None or blocks is None:
                    raise ValueError('Incomplete destination extent')
                if size is not None and (start + blocks) * block_size > size:
                    raise ValueError('Destination extent exceeds partition')
        partitions.append({'name': name, 'new_size_bytes': size,
                           'new_sha256_declared': new_hash.hex() or None,
                           'operation_counts': dict(sorted(counts.items())),
                           'source_dependency_declared': bool(requires_source),
                           'unknown_operations': unknown})
    if not partitions:
        raise ValueError('Manifest contains no partitions')
    return {'payload_major': major, 'payload_minor': minor,
            'manifest_size_bytes': manifest_size, 'metadata_hash_match': True,
            'metadata_signature_size_bytes': signature_size,
            'signature_verification': 'NOT_PERFORMED',
            'payload_kind_declared': 'FULL' if minor == 0 else 'DELTA',
            'partial_update_declared': bool(partial), 'block_size': block_size,
            'partitions': partitions,
            'total_new_partition_bytes_declared': sum(p['new_size_bytes'] or 0 for p in partitions),
            'reconstruction_verified': False,
            'stable_channel': 'UNVERIFIED', 'authorized_version': 'UNVERIFIED',
            'notes': ['Manifest only; no operation blobs decompressed or executed.',
                      'FULL describes update format, not a bootable VM or APK.',
                      'Declared hashes are not hashes of reconstructed images.']}
