#!/usr/bin/env python3
"""Reconstruct selected full-OTA partitions without mounting/executing firmware.

Supports only REPLACE, REPLACE_BZ and REPLACE_XZ. Every operation and output image
must match its declared SHA-256. Source-copy/delta/unknown operations fail closed.
Use on a stable local copy in an isolated workspace, never against a block device.
"""
import argparse
import bz2
import hashlib
import json
import lzma
from pathlib import Path
import struct
import zipfile

from tools.inspect_ota import inspect
from tools.payload_manifest import fields, one, repeated, read_exact

MAX_OPERATION = 64 * 1024 * 1024
MAX_TOTAL = 8 * 1024 * 1024 * 1024
DEFAULT_PARTITIONS = ('system', 'system_ext', 'vendor', 'product', 'odm')


def decode_operation(kind, blob, target_bytes):
    if not 0 < target_bytes <= MAX_OPERATION or len(blob) > MAX_OPERATION:
        raise ValueError('Operation exceeds resource limit')
    if kind == 0:
        output = blob
    elif kind in (1, 8):
        decoder = (bz2.BZ2Decompressor() if kind == 1 else
                   lzma.LZMADecompressor(memlimit=256 * 1024 * 1024))
        output = decoder.decompress(blob, max_length=target_bytes + 1)
        if not decoder.eof or decoder.unused_data:
            raise ValueError('Incomplete, oversized or concatenated compression stream')
    else:
        raise ValueError('Unsupported operation; no emulated success')
    if len(output) > target_bytes:
        raise ValueError('Decompressed data exceeds destination')
    return output.ljust(target_bytes, b'\0')


def reconstruct_partition(stream, data_start, payload_size, part, block_size, out):
    info = fields(one(part, 7, 2, b''))
    size = one(info, 1, 0)
    expected = one(info, 2, 2)
    if not size or size > MAX_TOTAL or expected is None or len(expected) != 32:
        raise ValueError('Missing/invalid output size or SHA-256')
    if one(part, 6, 2) is not None:
        raise ValueError('Delta partition not accepted')
    ranges = []
    plans = []
    for op in repeated(part, 8):
        kind = one(op, 1, 0)
        if kind not in (0, 1, 8) or op.get(4):
            raise ValueError('Source-dependent or unsupported operation')
        extents = []
        for extent in repeated(op, 6):
            start, count = one(extent, 1, 0), one(extent, 2, 0)
            if start is None or count is None or count <= 0:
                raise ValueError('Invalid destination extent')
            start, length = start * block_size, count * block_size
            if start + length > size:
                raise ValueError('Destination outside partition')
            ranges.append((start, start + length))
            extents.append((start, length))
        target_size = sum(length for _, length in extents)
        if not 0 < target_size <= MAX_OPERATION:
            raise ValueError('Invalid operation output size')
        offset, length = one(op, 2, 0, 0), one(op, 3, 0, 0)
        checksum = one(op, 8, 2)
        if not 0 < length <= MAX_OPERATION or data_start + offset + length > payload_size:
            raise ValueError('Invalid operation input range')
        if checksum is None or len(checksum) != 32:
            raise ValueError('Missing operation SHA-256')
        plans.append((kind, offset, length, checksum, extents, target_size))
    # Require complete, non-overlapping coverage for this deliberately narrow reader.
    end = 0
    for start, stop in sorted(ranges):
        if start != end:
            raise ValueError('Gap or overlap in destination coverage')
        end = stop
    if end != size:
        raise ValueError('Incomplete destination coverage')
    temporary = out.with_suffix('.img.part')
    if out.exists() or temporary.exists():
        raise ValueError('Refusing to overwrite an existing image')
    created = False
    try:
        with temporary.open('xb+') as image:
            created = True
            image.truncate(size)
            for kind, offset, length, checksum, extents, target_size in plans:
                stream.seek(data_start + offset)
                blob = read_exact(stream, length)
                if hashlib.sha256(blob).digest() != checksum:
                    raise ValueError('Operation SHA-256 mismatch')
                output = decode_operation(kind, blob, target_size)
                cursor = 0
                for start, length in extents:
                    image.seek(start)
                    image.write(output[cursor:cursor + length])
                    cursor += length
            image.flush()
            image.seek(0)
            digest = hashlib.sha256()
            while chunk := image.read(1024 * 1024):
                digest.update(chunk)
            if digest.digest() != expected:
                raise ValueError('Reconstructed partition SHA-256 mismatch')
            image.seek(0)
            prefix = image.read(4096)
        filesystem = ('ext4-family' if prefix[1080:1082] == b'\x53\xef' else
                      'erofs' if prefix[1024:1028] == b'\xe2\xe1\xf5\xe0' else 'UNKNOWN')
        temporary.rename(out)
        return {'size_bytes': size, 'sha256': digest.hexdigest(), 'sha256_match': True,
                'operations_verified': len(plans), 'filesystem_magic': filesystem}
    finally:
        if created:
            temporary.unlink(missing_ok=True)


def reconstruct(zip_path, destination, selected=DEFAULT_PARTITIONS):
    report = inspect(zip_path, include_manifest=True)
    manifest_report = report['payload_manifest']
    if manifest_report['payload_minor'] != 0 or manifest_report['partial_update_declared']:
        raise ValueError('Only full non-partial payloads accepted')
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=True)
    if destination.is_symlink() or any(destination.iterdir()):
        raise ValueError('Use an empty real output directory')
    selected = set(selected)
    known = {p['name']: p for p in manifest_report['partitions']}
    if not selected or not selected <= known.keys():
        raise ValueError('Unknown or empty partition selection')
    if sum(known[n]['new_size_bytes'] or MAX_TOTAL + 1 for n in selected) > MAX_TOTAL:
        raise ValueError('Selected images exceed total resource limit')
    outputs = {}
    with zipfile.ZipFile(zip_path) as archive, archive.open('payload.bin') as stream:
        header = read_exact(stream, 24)
        _, _, manifest_size, signature_size = struct.unpack('>4sQQI', header)
        manifest = fields(read_exact(stream, manifest_size))
        data_start = 24 + manifest_size + signature_size
        for part in repeated(manifest, 13):
            name = one(part, 1, 2).decode('utf-8')  # Already validated by inspector.
            if name in selected:
                outputs[name] = reconstruct_partition(stream, data_start,
                    archive.getinfo('payload.bin').file_size, part,
                    manifest_report['block_size'], destination / (name + '.img'))
    return {'source_zip_sha256': report['sha256'], 'partitions': outputs,
            'firmware_executed': False, 'images_mounted': False,
            'authenticity': 'UNVERIFIED', 'port_status': 'NOT PORTED YET'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('zip', type=Path)
    parser.add_argument('--directory', required=True, type=Path)
    parser.add_argument('--report', required=True, type=Path)
    args = parser.parse_args()
    result = reconstruct(args.zip, args.directory)
    args.report.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
