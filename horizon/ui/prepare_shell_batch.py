# SPDX-License-Identifier: GPL-3.0-only
"""Combine pinned JNI, thread, startup and frame candidates in a single analysis import."""
import argparse
import json
from pathlib import Path
from horizon.ui.prepare_shell import prepare as prepare_jni, select_symbols, executable_ranges, PREFIX
from tools.scan_partitions import command
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
    frame_evidence=json.loads(
        Path('analysis/builds/52168470052900520/shell-frame-decompilation.json').read_text())
    roots+=select(blob,frame_evidence,(
        (0xd8a5e8,0xd8a56c,'preferences library call_once callback'),
        (0xbe43c4,0xd622fc,'Clay frame preparation candidate'),
        (0xd8ec48,0xd622fc,'per-frame command handling candidate')))
    text,_=command(['readelf','--dyn-syms','-W',str(output/'libshell.so')])
    exports=select_symbols(text,[PREFIX+'nativeUserIdentityResponse',PREFIX+'nativeOnInteractionWindowChanged'])
    ranges=executable_ranges(blob)
    declarations=json.loads(Path('analysis/builds/52168470052900520/shell-jni-abi-proof.json').read_text())['native_declarations']
    for export in exports:
        if not any(a<=export['elf_address'] and export['elf_address']+export['size_bytes']<=b for a,b in ranges):
            raise ValueError('Additional JNI export outside executable memory')
        methods=[m for m in declarations if PREFIX+m['name']==export['symbol']]
        if len(methods)!=1 or not methods[0]['static']:raise ValueError('Missing exact DEX declaration')
        export['dex_descriptor']=methods[0]['descriptor']
    roots+=exports
    if len({r['elf_address'] for r in roots})!=len(roots) or len(roots)>32:
        raise ValueError('Invalid batch roots')
    (output/'shell-functions.txt').write_text(''.join(f"{r['elf_address']:x}\n" for r in roots))
    (output/'shell-batch-selection.json').write_text(json.dumps(dict(selected=roots,
        firmware_executed=False,private_abi_validated=False),indent=2)+'\n')

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('images','reconstruction','output'):parser.add_argument('--'+name,required=True)
    a=parser.parse_args();prepare(a.images,a.reconstruction,a.output)
