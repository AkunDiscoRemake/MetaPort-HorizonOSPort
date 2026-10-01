# SPDX-License-Identifier: GPL-3.0-only
"""Prepare just the verified tracking engine for focused static input analysis."""
import argparse
import json
import re
from pathlib import Path
from handtracking.ai.inspect_original import digest,input_string_targets
from tools.scan_partitions import command,dump_entry

ENGINE_SHA='10eac37188c97389dabfe7599a354d146d1e6223d849546d230796af93418ffe'


VISUAL_FIELDS = frozenset(('SkinningOffsets', 'SkinningWeights', 'RestPositions',
    'RestVertexNormals', 'TextureCoordinates', 'PreRotation', 'TranslationOffset',
    'RotationOrder', 'RestState', 'poseLibrary', 'firstChildJoint', 'handModel',
    'defaultfbx_L.msgpack', 'defaultfbx_R.msgpack', 'defaultfbx_restSkeletons.msgpack'))


def visual_string_targets(data, sections):
    section=re.search(r'\]\s+\.rodata\s+PROGBITS\s+([0-9a-f]+)\s+([0-9a-f]+)\s+([0-9a-f]+)',sections,re.I)
    if not section: return []
    address,offset,size=(int(x,16) for x in section.groups())
    if offset+size>len(data) or size>8*1024*1024: raise ValueError('Invalid rodata bounds')
    raw=data[offset:offset+size]; result=[]
    for match in re.finditer(rb'[ -~]{4,512}\x00',raw):
        if match.start() and raw[match.start()-1]!=0: continue
        text=match.group()[:-1].decode('ascii')
        if text in VISUAL_FIELDS or ('/handtracking/' in text and text.endswith('.msgpack')):
            result.append({'address':address+match.start(),'text':text})
    return result[:256]


def prepare(images,reconstruction,output):
    output.mkdir(parents=True,exist_ok=True)
    image=images/'odm.img'
    expected=json.loads(reconstruction.read_text())['partitions']['odm']
    if not expected['sha256_match'] or digest(image)!=expected['sha256']:raise ValueError('ODM verification failed')
    entries=json.loads(Path('analysis/builds/52168470052900520/static-analysis.json').read_text())['partitions']['odm']['entries']
    entry=next(e for e in entries if e['path']=='/lib64/libtrackingengines.so' and e['kind']=='file')
    binary=output/'libtrackingengines.so';dump_entry(image,entry,binary)
    if digest(binary)!=ENGINE_SHA:raise ValueError('Wrong tracking engine')
    sections,_=command(['readelf','-SW',str(binary)],max_output=1024*1024)
    (output/'visual-strings.json').write_text(json.dumps(visual_string_targets(binary.read_bytes(),sections)))
    (output/'visual-functions.txt').write_text('')
    (output/'input-strings.json').write_text(json.dumps(input_string_targets(binary.read_bytes(),sections)))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('images','reconstruction','output'):p.add_argument('--'+name,required=True,type=Path)
    a=p.parse_args();prepare(a.images,a.reconstruction,a.output)
