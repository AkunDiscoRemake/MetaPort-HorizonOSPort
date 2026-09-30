# SPDX-License-Identifier: GPL-3.0-only
"""Prepare hash-pinned original VrShell renderer for static hand-function recovery."""
import argparse
import json
from pathlib import Path
import struct
import tempfile
import zipfile
from horizon.tracking.inspect_original import BUILD, digest
from horizon.tracking.hand_presentation import inspect_apk
from tools.scan_partitions import dump_entry

SHELL_SHA='2d4c274bc81c9f545f3b5571ba57643a9696333e8f6b3a125e45682fbd96dce0'
SHELL_SIZE=41235512
MEMBER='lib/arm64-v8a/libshell.so'


def file_offset_va(blob, offset):
    if type(offset) is not int or not 0<=offset<len(blob):raise ValueError('File offset')
    if len(blob)<64 or blob[:6]!=b'\x7fELF\x02\x01' or struct.unpack_from('<H',blob,18)[0]!=183:
        raise ValueError('Expected little-endian AArch64 ELF64')
    phoff=struct.unpack_from('<Q',blob,32)[0]
    entsize,count=struct.unpack_from('<HH',blob,54)
    if entsize!=56 or not 0<count<=256 or phoff+count*entsize>len(blob):
        raise ValueError('Program header bounds')
    matches=[]
    for i in range(count):
        kind,flags,start,va,physical,size,memsize,align=struct.unpack_from('<IIQQQQQQ',blob,phoff+i*56)
        if kind!=1:continue
        if start+size>len(blob) or size>memsize or va+memsize>1<<64:
            raise ValueError('Load segment bounds')
        if start<=offset<start+size:matches.append(va+offset-start)
    if len(matches)!=1:raise ValueError('Unmapped or ambiguous file offset')
    return matches[0]


def prepare(images,reconstruction,output):
    image=images/'system_ext.img';expected=json.loads(reconstruction.read_text())['partitions']['system_ext']
    if not expected['sha256_match'] or image.stat().st_size!=expected['size_bytes'] or digest(image)!=expected['sha256']:
        raise ValueError('Unverified system_ext')
    policy=json.loads(Path(f'analysis/builds/{BUILD}/hand-ui-report.json').read_text())
    original=next(a for a in policy['ui'] if a['path']=='/priv-app/VrShell/VrShell.apk')
    entries=json.loads(Path(f'analysis/builds/{BUILD}/static-analysis.json').read_text())['partitions']['system_ext']['entries']
    found=[e for e in entries if e['kind']=='file' and e['path']==original['path']]
    if len(found)!=1:raise ValueError('VrShell inventory mismatch')
    with tempfile.TemporaryDirectory() as folder:
        apk=Path(folder)/'original.apk';dump_entry(image,found[0],apk)
        if apk.stat().st_size!=original['size'] or digest(apk)!=original['sha256']:
            raise ValueError('Wrong VrShell')
        evidence=inspect_apk(apk)
        member=next(x for x in evidence['native_contracts'] if x['name']==MEMBER)
        if member.get('sha256')!=SHELL_SHA or member['size_bytes']!=SHELL_SIZE:
            raise ValueError('Wrong renderer')
        if member.get('strings_truncated'):raise ValueError('Renderer target evidence truncated')
        with zipfile.ZipFile(apk) as archive:blob=archive.read(MEMBER)
    targets=[{'address':file_offset_va(blob,s['file_offset']),'text':s['text']} for s in member['strings']]
    # Prefer actual mesh acquisition and visual-state controls over RTTI/null fallback names.
    targets.sort(key=lambda x:(not any(s in x['text'] for s in
        ('xrGetHandMeshFB','xrLocateHandJointsEXT','ShellHandMaterial.', 'CoHandRenderBehavior.cpp',
         'Invalid hand index','Unexpected number of hand skeleton joints')),x['address']))
    output.mkdir(parents=True,exist_ok=True)
    (output/'libshell.so').write_bytes(blob)
    (output/'render-strings.json').write_text(json.dumps(targets,indent=2)+'\n')
    # Callees observed in renderer run 36778979923; ELF VAs (Ghidra base removed).
    # These are NOT exports or validated C++ entry-point declarations.
    helpers=(0x9bac58,0x9428e4,0x9bad24,0x9b9ed8,0x14377c4,0xcc3b5c)
    (output/'render-functions.txt').write_text(''.join(f'{address:x}\n' for address in helpers))
    return targets


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('images','reconstruction','output'):p.add_argument('--'+name,required=True,type=Path)
    a=p.parse_args();prepare(a.images,a.reconstruction,a.output)
