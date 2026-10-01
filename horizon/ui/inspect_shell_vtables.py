# SPDX-License-Identifier: GPL-3.0-only
"""Bounded static windows around two constructor-derived vptr candidates.

Not vtable extents, signatures, ownership rules, or executable ABI adapters.
Packed relocations and relative vtables remain unresolved; raw words may be data.
"""
import argparse
import hashlib
import json
from pathlib import Path
import struct
from handtracking.ai.elf_pointer_evidence import load_segments, parse_relocations
from tools.scan_partitions import command

POLICY = Path(__file__).with_name('shell-policy.json')
CANDIDATES = (
    {'constructor_elf': 0x111fb2c, 'address_point_elf': 0x2602b40},
    {'constructor_elf': 0xdaebf0, 'address_point_elf': 0x25c2cc8},
)


def windows(data, relocations, candidates=CANDIDATES, slots=32):
    if not 1 <= slots <= 64 or len(candidates) > 16:
        raise ValueError('Window budget')
    segments = load_segments(data)
    output = []
    for candidate in candidates:
        address = candidate['address_point_elf']
        if address % 8 or not 16 <= address < (1 << 64) - slots * 8:
            raise ValueError('Address point bounds/alignment')
        rows = []
        # Two preceding words are included without assuming Itanium RTTI layout.
        for index in range(-2, slots):
            slot = address + index * 8
            seg = next((s for s in segments if s['va'] <= slot and
                        slot + 8 <= s['va'] + s['filesz']), None)
            if seg is None:
                rows.append({'slot_elf': slot, 'kind': 'UNMAPPED_OR_BSS'})
                continue
            raw = struct.unpack_from('<Q', data, seg['offset'] + slot - seg['va'])[0]
            value, kind = relocations.get(slot, (raw, 'RAW64_CANDIDATE'))
            executable = value % 4 == 0 and any(
                s['flags'] & 1 and s['va'] <= value < s['va'] + s['filesz']
                for s in segments)
            rows.append({'slot_elf': slot, 'relative_byte_offset': index * 8,
                         'raw_u64': raw, 'candidate_target_elf': value, 'kind': kind,
                         'points_into_file_backed_executable_segment': executable})
        output.append({**candidate, 'slots': rows})
    return {'windows': output, 'vtable_extent_validated': False,
            'private_abi_validated': False, 'firmware_executed': False,
            'scope': 'Adjacent raw/RELATIVE/local ABS64 words, not proven functions; symbol interposition and packed relocations unresolved'}


def run(library, output):
    library = Path(library)
    policy = json.loads(POLICY.read_text())
    if library.stat().st_size != policy['library_size_bytes']:
        raise ValueError('Unpinned library size')
    data = library.read_bytes()
    if hashlib.sha256(data).hexdigest() != policy['library_sha256']:
        raise ValueError('Unpinned library hash')
    text, diagnostic = command(['readelf', '-rW', str(library)], max_output=64*1024*1024)
    relocations, coverage = parse_relocations(text)
    report = windows(data, relocations)
    report.update(library_sha256=policy['library_sha256'], relocations=coverage,
                  readelf_diagnostics=diagnostic,
                  source_evidence='shell-platform-runtime-decompilation.json; Ghidra base 0x100000 subtracted from DAT references')
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + '\n')
    return report


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--library', required=True)
    p.add_argument('--output', required=True)
    a = p.parse_args()
    run(a.library, a.output)
