# SPDX-License-Identifier: GPL-3.0-only
"""Combine pinned JNI, thread, startup and frame candidates in a single analysis import."""
import argparse
import json
from pathlib import Path
from horizon.ui.prepare_shell import prepare as prepare_jni
from horizon.ui.prepare_shell_threads import select, EVIDENCE as THREAD_SOURCE, TARGETS as THREADS
from horizon.ui.prepare_shell_frames import EVIDENCE as FRAME_SOURCE, TARGETS as FRAMES


def prepare(images,reconstruction,output):
    output=Path(output)
    roots=prepare_jni(images,reconstruction,output)
    blob=(output/'libshell.so').read_bytes()
    roots+=select(blob,json.loads(THREAD_SOURCE.read_text()),THREADS)
    roots+=select(blob,json.loads(FRAME_SOURCE.read_text()),FRAMES+(
        (0xd5d3d8,0xd8a0b4,'ShellApp construction and frame loop'),
        (0xd8e01c,0xd8a0b4,'ShellApp destruction')))
    if len({r['elf_address'] for r in roots})!=len(roots) or len(roots)>32:
        raise ValueError('Invalid batch roots')
    (output/'shell-functions.txt').write_text(''.join(f"{r['elf_address']:x}\n" for r in roots))
    (output/'shell-batch-selection.json').write_text(json.dumps(dict(selected=roots,
        firmware_executed=False,private_abi_validated=False),indent=2)+'\n')

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('images','reconstruction','output'):parser.add_argument('--'+name,required=True)
    a=parser.parse_args();prepare(a.images,a.reconstruction,a.output)
