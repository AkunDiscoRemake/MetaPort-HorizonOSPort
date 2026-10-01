# SPDX-License-Identifier: GPL-3.0-only
"""Follow actual platform/Clay constructor and initialization calls, not options builders."""
import argparse
import hashlib
import json
from pathlib import Path
from horizon.ui.prepare_shell import prepare as prepare_jni
from horizon.ui.prepare_shell_threads import select

EVIDENCE=Path('analysis/builds/52168470052900520/shell-thread-decompilation.json')
TARGETS=((0x111fb2c,0xd5d3d8,'constructor for object assigned to VrPlatform slot candidate'),
         (0xbbd334,0xd5d3d8,'Clay init status candidate'),
         (0x1b5ed50,0xd5d3d8,'Clay start status candidate'),
         (0xdaebf0,0xd5d3d8,'default aligned Clay object construction candidate'))


def prepare(images,reconstruction,output):
    output=Path(output);prepare_jni(images,reconstruction,output)
    raw=EVIDENCE.read_bytes()
    selected=select((output/'libshell.so').read_bytes(),json.loads(raw),TARGETS)
    (output/'shell-functions.txt').write_text(''.join(f"{r['elf_address']:x}\n" for r in selected))
    (output/'shell-platform-runtime-selection.json').write_text(json.dumps(dict(selected=selected,
        evidence_sha256=hashlib.sha256(raw).hexdigest(),firmware_executed=False,
        scope='C-like reference candidates; signatures and vtable layout unvalidated'),indent=2)+'\n')

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('images','reconstruction','output'):p.add_argument('--'+name,required=True)
    a=p.parse_args();prepare(a.images,a.reconstruction,a.output)
