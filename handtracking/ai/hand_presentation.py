# SPDX-License-Identifier: GPL-3.0-only
"""Locate original VrShell hand presentation resources/contracts, without execution.

Names and strings are candidates, not proof of use or an implemented renderer.
No ZIP member is extracted to a member-controlled filesystem path.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile
import zipfile
from handtracking.ai.inspect_original import BUILD, digest
from tools.scan_partitions import dump_entry

MEMBER = re.compile(r'(?:^|[/_.-])(?:hands?|handtracking|gestures?|skeletons?|animations?|shaders?|materials?)(?:[/_.-]|$)',re.I)
NATIVE = re.compile(r'lib[^/]*(?:vrshell|shell|openxr|ovr|hand)[^/]*\.so$',re.I)
CONTRACT = re.compile(r'xr(?:CreateHandTracker|LocateHandJoints|GetHandMesh|DestroyHandTracker)|XR_(?:EXT|FB|META|MSFT)_hand_|hand.?mesh|hand.?skeleton|hand.?material|hand.?shader|hand.?visual|hand.?render|hand.?skinning',re.I)
MAX_NATIVE = 192*1024*1024
MAX_TOTAL = 512*1024*1024


def inspect_apk(path):
    result={'candidate_resources':[],'native_contracts':[],'renderer_integrated':False,
            'candidate_names_prove_usage':False,'firmware_executed':False}
    with zipfile.ZipFile(path) as archive:
        members=archive.infolist()
        if len(members)>100000: raise ValueError('APK member count')
        names=[m.filename for m in members]
        if len(set(names))!=len(names):raise ValueError('Duplicate ZIP member')
        total=0; matched=0
        for member in members:
            if member.is_dir():continue
            if MEMBER.search(member.filename):
                matched+=1
                if len(result['candidate_resources'])<256:
                    result['candidate_resources'].append({'name':member.filename,
                        'size_bytes':member.file_size,'compressed_bytes':member.compress_size})
            if not member.filename.startswith('lib/arm64-v8a/') or not NATIVE.search(member.filename):continue
            row={'name':member.filename,'size_bytes':member.file_size};result['native_contracts'].append(row)
            if member.file_size>MAX_NATIVE or total+member.file_size>MAX_TOTAL:
                row['status']='SIZE_LIMIT_NOT_SCANNED';continue
            blob=archive.read(member);total+=len(blob)
            if not blob.startswith(b'\x7fELF'):raise ValueError('Expected ELF native member')
            row['sha256']=hashlib.sha256(blob).hexdigest()
            matches=[];count=0
            for match in re.finditer(rb'[ -~]{4,512}\x00',blob):
                if match.start() and blob[match.start()-1]!=0:continue
                text=match.group()[:-1].decode('ascii')
                if CONTRACT.search(text):
                    count+=1
                    if len(matches)<128:matches.append({'file_offset':match.start(),'text':text})
            row.update(status='STATIC_STRINGS_ONLY',matching_string_count=count,
                       strings=matches,strings_truncated=count>len(matches))
        result.update(members=len(members),matching_resource_count=matched,
                      resources_truncated=matched>len(result['candidate_resources']),
                      native_bytes_scanned=total)
    return result


def inspect(images,reconstruction,output):
    image=images/'system_ext.img'
    expected=json.loads(reconstruction.read_text())['partitions']['system_ext']
    if not expected['sha256_match'] or image.stat().st_size!=expected['size_bytes'] or digest(image)!=expected['sha256']:
        raise ValueError('Unverified system_ext')
    policy=json.loads(Path(f'analysis/builds/{BUILD}/hand-ui-report.json').read_text())
    original=next(a for a in policy['ui'] if a['path']=='/priv-app/VrShell/VrShell.apk')
    entries=json.loads(Path(f'analysis/builds/{BUILD}/static-analysis.json').read_text())['partitions']['system_ext']['entries']
    found=[e for e in entries if e['kind']=='file' and e['path']==original['path']]
    if len(found)!=1:raise ValueError('Missing or duplicate VrShell inventory')
    with tempfile.TemporaryDirectory() as folder:
        apk=Path(folder)/'original.apk';dump_entry(image,found[0],apk)
        if apk.stat().st_size!=original['size'] or digest(apk)!=original['sha256']:
            raise ValueError('Wrong original VrShell')
        report=inspect_apk(apk)
    report.update(build=BUILD,apk_sha256=original['sha256'],source_commit=os.environ.get('GITHUB_SHA'),
                  workflow_run=os.environ.get('GITHUB_RUN_ID'),port_status='NOT PORTED YET')
    output.mkdir(parents=True,exist_ok=True)
    (output/'hand-presentation-report.json').write_text(json.dumps(report,indent=2)+'\n')
    return report


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('images','reconstruction','output'):p.add_argument('--'+name,required=True,type=Path)
    a=p.parse_args();inspect(a.images,a.reconstruction,a.output)
