# SPDX-License-Identifier: GPL-3.0-only
"""Inspect four original shell platform dependencies; never load native code."""
import argparse
import json
from pathlib import Path
import tempfile
from handtracking.ai.inspect_original import digest, BUILD
from tools.scan_partitions import dump_entry, elf_report
from horizon.ui.prepare_shell import POLICY

TARGETS={'system_ext':['/lib64/libhzos.meta.so','/lib64/libhzos_spaces.meta.so'],
         'system':['/system/lib64/libbase.so','/system/lib64/libc++.so']}


def verify_partition(image, expected):
    if not expected['sha256_match'] or image.stat().st_size!=expected['size_bytes'] or digest(image)!=expected['sha256']:
        raise ValueError('Unverified original partition')


def inspect(images,reconstruction,output):
    images=Path(images);output=Path(output);output.parent.mkdir(parents=True,exist_ok=True)
    recon=json.loads(Path(reconstruction).read_text());policy=json.loads(POLICY.read_text())
    if recon['source_zip_sha256']!=policy['ota_sha256']:raise ValueError('Wrong firmware provenance')
    inv=json.loads(Path(f'analysis/builds/{BUILD}/static-analysis.json').read_text())['partitions']
    r={'build':BUILD,'source_ota_sha256':policy['ota_sha256'],'firmware_executed':False,
       'apk_linkable':False,'private_abi_validated':False,'libraries':[]}
    for partition,paths in TARGETS.items():
        image=images/(partition+'.img');verify_partition(image,recon['partitions'][partition])
        for path in paths:
            entries=[e for e in inv[partition]['entries'] if e['kind']=='file' and e['path']==path]
            if len(entries)!=1:raise ValueError('Ambiguous library inventory')
            with tempfile.TemporaryDirectory() as d:
                library=Path(d)/'library.so';dump_entry(image,entries[0],library)
                info=elf_report(library,deep=False)
                if info.get('machine')!='AArch64':raise ValueError('Wrong ELF architecture')
                info.update(partition=partition,path=path,partition_sha256=recon['partitions'][partition]['sha256'])
                r['libraries'].append(info)
                output.write_text(json.dumps(r,indent=2)+'\n')
    return r

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('images','reconstruction','output'):p.add_argument('--'+name,required=True)
    a=p.parse_args();inspect(a.images,a.reconstruction,a.output)
