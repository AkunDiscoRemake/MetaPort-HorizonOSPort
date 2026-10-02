# SPDX-License-Identifier: GPL-3.0-only
"""Extract two hash-pinned original focus ELFs for host-only decompilation."""
import argparse
import hashlib
import json
from pathlib import Path
import struct
from horizon.ui.prepare_shell import POLICY
from horizon.ui.prepare_shell_apk import verify_partition
from handtracking.ai.inspect_original import BUILD
from tools.scan_partitions import dump_entry

INPUTS=(
    ('/bin/vrfocusserver',258304,'14289b0fca87a4b4fbcd1e0b1a06cd8035ebf8686551f86a3517ad08deaea418'),
    ('/lib64/libvrfocus_interface-cpp.so',67808,'949bebe7639f07ec86c818456a41c403e6a946ed9073b162b3d46ee29291916c'),
)


def verify_elf(data,size,sha):
    if len(data)!=size or hashlib.sha256(data).hexdigest()!=sha:
        raise ValueError('Wrong pinned focus ELF')
    if len(data)<64 or data[:6]!=b'\x7fELF\x02\x01' or struct.unpack_from('<HH',data,16)!=(3,183):
        raise ValueError('Expected little-endian AArch64 ET_DYN input')


def prepare(images,reconstruction,output):
    policy=json.loads(POLICY.read_text());recon=json.loads(Path(reconstruction).read_text())
    verify_partition(images,'system_ext',recon,policy)
    entries=json.loads(Path(f'analysis/builds/{BUILD}/static-analysis.json').read_text())['partitions']['system_ext']['entries']
    output=Path(output);output.mkdir(parents=True,exist_ok=True);rows=[]
    for source,size,sha in INPUTS:
        matches=[e for e in entries if e['path']==source and e['kind']=='file' and e['size_bytes']==size]
        if len(matches)!=1:raise ValueError('Focus ELF inventory mismatch')
        target=output/Path(source).name
        dump_entry(Path(images)/'system_ext.img',matches[0],target)
        verify_elf(target.read_bytes(),size,sha)
        rows.append({'path':source,'sha256':sha,'size_bytes':size,'host_file':target.name})
    report={'inputs':rows,'source_image_sha256':recon['partitions']['system_ext']['sha256'],
            'firmware_executed':False,'apk_modified':False,
            'scope':'Original daemon and native Binder interface, not an app service implementation'}
    (output/'focus-native-inputs.json').write_text(json.dumps(report,indent=2)+'\n')

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('images','reconstruction','output'):parser.add_argument('--'+name,required=True)
    a=parser.parse_args();prepare(a.images,a.reconstruction,a.output)
