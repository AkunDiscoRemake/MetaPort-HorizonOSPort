# SPDX-License-Identifier: GPL-3.0-only
"""Select internal callback/lifecycle candidates from pinned prior analysis.

Names are analysis labels, not original symbols or validated ABI contracts.
"""
import argparse
import hashlib
import json
from pathlib import Path
from horizon.ui.prepare_shell import POLICY, executable_ranges

EVIDENCE=Path('analysis/builds/52168470052900520/shell-startup-decompilation.json')
TARGETS=((0xd8a0b4,0xd89758,'thread target candidate'),
         (0xd8aa48,0xd89758,'pthread trampoline candidate'),
         (0xd8a254,0xd78e08,'service destruction candidate'),
         (0xd8a6d8,0xd89758,'preferences symbol lookup candidate'),
         (0xd8a078,0xd89758,'thread lifecycle candidate'))


def select(blob,evidence):
    policy=json.loads(POLICY.read_text())
    if hashlib.sha256(blob).hexdigest()!=policy['library_sha256']:
        raise ValueError('Unpinned library')
    if evidence['program_sha256'].lower()!=policy['library_sha256']:
        raise ValueError('Unpinned reference analysis')
    base=int(evidence['image_base'],16)
    ranges=executable_ranges(blob)
    selected=[]
    for address,caller,purpose in TARGETS:
        functions=[f for f in evidence['functions'] if f['elf_address']==caller]
        label=f'FUN_{address+base:08x}'
        if len(functions)!=1 or label not in functions[0]['c_like']:
            raise ValueError('Missing prior reference')
        if address%4 or not any(a<=address and address+4<=b for a,b in ranges):
            raise ValueError('Candidate outside executable bytes')
        selected.append(dict(elf_address=address,referencing_function_elf_va=caller,
                             analysis_label=label,purpose=purpose))
    return selected


def prepare(output):
    output=Path(output);raw=EVIDENCE.read_bytes()
    selected=select((output/'libshell.so').read_bytes(),json.loads(raw))
    (output/'shell-functions.txt').write_text(''.join(f"{x['elf_address']:x}\n" for x in selected))
    (output/'shell-thread-selection.json').write_text(json.dumps(dict(
        selected=selected,evidence_path=str(EVIDENCE),evidence_sha256=hashlib.sha256(raw).hexdigest(),
        scope='Candidate addresses referenced by prior decompilation; not validated function signatures',
        firmware_executed=False,abi_validated=False),indent=2)+'\n')

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',required=True)
    prepare(p.parse_args().output)
