# SPDX-License-Identifier: GPL-3.0-only
"""Select original startup/frame candidates; not callable ABI declarations."""
import argparse
import hashlib
import json
from pathlib import Path
from horizon.ui.prepare_shell_threads import select

EVIDENCE=Path('analysis/builds/52168470052900520/shell-thread-decompilation.json')
TARGETS=((0xd61360,0xd5d3d8,'identity readiness candidate'),
         (0xd622fc,0xd5d3d8,'frame iteration candidate'),
         (0xd8bb74,0xd5d3d8,'Clay construction candidate'),
         (0xd8bc20,0xd5d3d8,'Clay initialization candidate'),
         (0xd8befc,0xd5d3d8,'Clay startup candidate'),
         (0xdc8480,0xd5d3d8,'platform-related construction candidate'),
         (0xd8a760,0xd8a6d8,'preferences call_once callback'),
         (0xd8b8bc,0xd5d3d8,'platform configuration candidate'))


def prepare(output):
    output=Path(output);raw=EVIDENCE.read_bytes()
    selected=select((output/'libshell.so').read_bytes(),json.loads(raw),TARGETS)
    (output/'shell-functions.txt').write_text(''.join(f"{x['elf_address']:x}\n" for x in selected))
    (output/'shell-frame-selection.json').write_text(json.dumps(dict(
        selected=selected,evidence_path=str(EVIDENCE),evidence_sha256=hashlib.sha256(raw).hexdigest(),
        scope='Prior decompilation references only; inferred purpose and ABI unvalidated',
        firmware_executed=False,abi_validated=False),indent=2)+'\n')

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',required=True)
    prepare(parser.parse_args().output)
