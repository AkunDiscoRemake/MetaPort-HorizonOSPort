# SPDX-License-Identifier: GPL-3.0-only
"""Select original executable targets from bounded constructor-adjacent windows.

These are not validated vtable extents, function signatures, or runtime adapters.
"""
import argparse
import hashlib
import json
from pathlib import Path
from horizon.ui.prepare_shell import prepare as prepare_jni, POLICY
from horizon.ui.inspect_shell_vtables import run as inspect_windows


def select(report, expected_hash):
    if report['library_sha256'] != expected_hash:
        raise ValueError('Wrong original library')
    if report['private_abi_validated'] is not False or report['firmware_executed'] is not False:
        raise ValueError('Unsupported evidence claims')
    targets = {}
    for window in report['windows']:
        for slot in window['slots']:
            offset = slot.get('relative_byte_offset', -1)
            if not 0 <= offset < 32*8 or offset % 8:
                continue
            if slot.get('points_into_file_backed_executable_segment') is not True:
                continue
            address = slot['candidate_target_elf']
            if not isinstance(address, int) or address <= 0 or address % 4:
                raise ValueError('Invalid executable candidate')
            row = targets.setdefault(address, {'elf_address':address, 'references':[],
                                               'signature_validated':False})
            row['references'].append({'constructor_elf':window['constructor_elf'],
                                      'address_point_elf':window['address_point_elf'],
                                      'relative_byte_offset':offset, 'kind':slot['kind']})
    if not 1 <= len(targets) <= 64:
        raise ValueError('Empty or excessive candidate frontier')
    return list(targets.values())


def prepare(images, reconstruction, output):
    output = Path(output)
    prepare_jni(images, reconstruction, output)
    evidence = output/'shell-vtable-windows.json'
    report = inspect_windows(output/'libshell.so', evidence)
    selected = select(report, json.loads(POLICY.read_text())['library_sha256'])
    (output/'shell-functions.txt').write_text(''.join(f"{r['elf_address']:x}\n" for r in selected))
    (output/'shell-virtuals-selection.json').write_text(json.dumps({
        'selected':selected, 'evidence_sha256':hashlib.sha256(evidence.read_bytes()).hexdigest(),
        'firmware_executed':False, 'private_abi_validated':False,
        'scope':'Constructor-adjacent executable pointer candidates; no established vtable extent'
    }, indent=2)+'\n')


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('images','reconstruction','output'):
        p.add_argument('--'+name,required=True)
    a = p.parse_args()
    prepare(a.images, a.reconstruction, a.output)
