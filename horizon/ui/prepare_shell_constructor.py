# SPDX-License-Identifier: GPL-3.0-only
"""Retry one original constructor without repeating the whole 96-function frontier."""
import argparse
import json
from pathlib import Path
from horizon.ui.prepare_shell import prepare as prepare_jni
from horizon.ui.prepare_shell_threads import select
from horizon.ui.prepare_shell_frames import EVIDENCE


def prepare(images,reconstruction,output):
    output=Path(output);prepare_jni(images,reconstruction,output)
    selected=select((output/'libshell.so').read_bytes(),json.loads(EVIDENCE.read_text()),
                    ((0xdc8480,0xd5d3d8,'constructor retry after timeout and response-buffer limit'),))
    (output/'shell-functions.txt').write_text('dc8480\n')
    (output/'shell-constructor-selection.json').write_text(json.dumps(dict(selected=selected,
        firmware_executed=False,private_abi_validated=False),indent=2)+'\n')

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('images','reconstruction','output'):p.add_argument('--'+name,required=True)
    a=p.parse_args();prepare(a.images,a.reconstruction,a.output)
