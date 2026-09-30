# SPDX-License-Identifier: GPL-3.0-only
"""Bounded ORIGINAL-engine optimization leads, never proof of runtime activation."""
import hashlib
import json
from pathlib import Path
import re
from horizon.tracking.prepare_input import ENGINE_SHA
from tools.scan_partitions import command

GROUPS = {
    'inference': r'quantiz|uint8|float16|int8|hexagon|boltnn|xnnpack|delegate|batch|tensor.*contigu',
    'memory': r'zero.copy|buffer.*reus|memory.plan|arena.alloc|aligned_alloc|prealloc|memory.pool|cache.*tensor',
    'temporal': r'predict|smooth|filter|thread.pool|affinity|schedul|frame.*skip|downsampl|roi|region.of.interest',
}
HAND = re.compile(r'handtracking|hand_tracking|hand[ /:_-]|\bdpe\b|dpetorch|\bskb\b|\bstp\b', re.I)


def scan(data, sections):
    m = re.search(r'\]\s+\.rodata\s+PROGBITS\s+([0-9a-f]+)\s+([0-9a-f]+)\s+([0-9a-f]+)', sections, re.I)
    if not m:
        raise ValueError('Missing rodata')
    va, offset, size = (int(x, 16) for x in m.groups())
    if offset + size > len(data) or size > 8 * 1024 * 1024:
        raise ValueError('Invalid rodata bounds')
    raw = data[offset:offset+size]
    groups = {name: [] for name in GROUPS}
    for match in re.finditer(rb'[ -~]{4,512}\x00', raw):
        if match.start() and raw[match.start()-1] != 0:
            continue
        text = match.group()[:-1].decode('ascii')
        for name, pattern in GROUPS.items():
            if re.search(pattern, text, re.I):
                groups[name].append({'address': va + match.start(), 'text': text,
                                     'hand_context_in_string': bool(HAND.search(text))})
    result = {}
    for name, rows in groups.items():
        rows.sort(key=lambda row: (not row['hand_context_in_string'], row['address']))
        result[name] = {'matched_count': len(rows), 'selected': rows[:64],
                        'truncated': len(rows) > 64}
    return result


def prepare(output):
    output = Path(output)
    binary = output/'libtrackingengines.so'
    data = binary.read_bytes()
    if hashlib.sha256(data).hexdigest() != ENGINE_SHA:
        raise ValueError('Wrong engine; refusing fixed function addresses')
    sections, _ = command(['readelf', '-SW', str(binary)])
    groups = scan(data, sections)
    for name, group in groups.items():
        (output/f'{name}-strings.json').write_text(json.dumps(group['selected'], indent=2)+'\n')
        # Observed V1 load/configure helper; V2 executor. Not exported ABI entries.
        addresses = (0x1618660, 0x162bee0) if name == 'inference' else ()
        (output/f'{name}-functions.txt').write_text(''.join(f'{address:x}\n' for address in addresses))
    report = {'engine_sha256': ENGINE_SHA, 'groups': groups, 'all_optimizations_found': False,
              'runtime_validated': False, 'scope': 'String leads, including generic dependencies; call-chain validation required'}
    (output/'hand-optimization-targets.json').write_text(json.dumps(report, indent=2)+'\n')
    return report


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', type=Path)
    prepare(parser.parse_args().output)
