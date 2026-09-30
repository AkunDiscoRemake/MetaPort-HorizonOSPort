# SPDX-License-Identifier: GPL-3.0-only
"""Prepare ORIGINAL shared tracking-service scheduler/memory paths, not a phone service."""
import json
import re
from pathlib import Path
from horizon.tracking.inspect_original import BUILD, digest
from tools.scan_partitions import command, dump_entry

SERVICE_SHA='a6474bc3710558a26827a5165556a99cd998b013233072eefe4edf2b6b2f1945'
SERVICE_SIZE=5384496
PATTERN=re.compile(r'hand|trackingPolicy|wake_affine|cpuset|schedul|affinity|priority|thread|memorybroker|buffer|zero.copy|deadline|frame.*drop',re.I)
PRIORITY=re.compile(r'hand|trackingPolicy|wake_affine|cpuset|schedul|affinity|priority',re.I)


def service_targets(data,sections):
    m=re.search(r'\]\s+\.rodata\s+PROGBITS\s+([0-9a-f]+)\s+([0-9a-f]+)\s+([0-9a-f]+)',sections,re.I)
    if not m: raise ValueError('Missing rodata')
    va,offset,size=(int(x,16) for x in m.groups())
    if offset+size>len(data) or size>8*1024*1024: raise ValueError('Invalid rodata bounds')
    raw=data[offset:offset+size];rows=[]
    for match in re.finditer(rb'[ -~]{4,512}\x00',raw):
        if match.start() and raw[match.start()-1]!=0: continue
        text=match.group()[:-1].decode('ascii')
        if PATTERN.search(text): rows.append({'address':va+match.start(),'text':text})
    rows.sort(key=lambda r:(not bool(PRIORITY.search(r['text'])),r['address']))
    return {'matched_count':len(rows),'selected':rows[:128],'truncated':len(rows)>128,
            'hand_exclusive':False,'runtime_activated':False}


def prepare(images,reconstruction,output):
    image=Path(images)/'odm.img';expected=json.loads(Path(reconstruction).read_text())['partitions']['odm']
    if not expected['sha256_match'] or image.stat().st_size!=expected['size_bytes'] or digest(image)!=expected['sha256']:
        raise ValueError('Unverified ODM')
    inventory=json.loads(Path(f'analysis/builds/{BUILD}/static-analysis.json').read_text())['partitions']['odm']['entries']
    entries=[e for e in inventory if e['path']=='/bin/trackingservice' and e['kind']=='file']
    if len(entries)!=1: raise ValueError('Service inventory mismatch')
    output=Path(output);output.mkdir(parents=True,exist_ok=True)
    binary=output/'trackingservice';dump_entry(image,entries[0],binary)
    if binary.stat().st_size!=SERVICE_SIZE or digest(binary)!=SERVICE_SHA: raise ValueError('Wrong tracking service')
    sections,_=command(['readelf','-SW',str(binary)])
    report=service_targets(binary.read_bytes(),sections)
    report['program_sha256']=SERVICE_SHA
    (output/'service-functions.txt').write_text('')
    (output/'service-strings.json').write_text(json.dumps(report['selected'],indent=2)+'\n')
    (output/'hand-service-targets.json').write_text(json.dumps(report,indent=2)+'\n')
    return report
