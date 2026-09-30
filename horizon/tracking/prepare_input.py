# SPDX-License-Identifier: GPL-3.0-only
"""Prepare just the verified tracking engine for focused static input analysis."""
import argparse
import json
from pathlib import Path
from horizon.tracking.inspect_original import digest,input_string_targets
from tools.scan_partitions import command,dump_entry

ENGINE_SHA='10eac37188c97389dabfe7599a354d146d1e6223d849546d230796af93418ffe'


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
    (output/'input-strings.json').write_text(json.dumps(input_string_targets(binary.read_bytes(),sections)))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('images','reconstruction','output'):p.add_argument('--'+name,required=True,type=Path)
    a=p.parse_args();prepare(a.images,a.reconstruction,a.output)
