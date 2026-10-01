# SPDX-License-Identifier: GPL-3.0-only
"""Prepare exact original surface and space exports for static ABI recovery."""
import argparse
import json
from pathlib import Path
from handtracking.ai.inspect_original import digest, BUILD
from horizon.ui.prepare_shell import POLICY, select_symbols, executable_ranges
from horizon.ui.inspect_platform import verify_partition
from tools.scan_partitions import command, dump_entry

def prepare(images,reconstruction,output):
    output=Path(output);output.mkdir(parents=True,exist_ok=True)
    recon=json.loads(Path(reconstruction).read_text())
    if recon['source_zip_sha256']!=json.loads(POLICY.read_text())['ota_sha256']:raise ValueError('Wrong OTA')
    image=Path(images)/'system_ext.img';verify_partition(image,recon['partitions']['system_ext'])
    inv=json.loads(Path(f'analysis/builds/{BUILD}/static-analysis.json').read_text())['partitions']['system_ext']['entries']
    policy=json.loads(Path(__file__).with_name('platform-native-policy.json').read_text());rows=[]
    for lib in policy['libraries']:
        if lib['partition']!='system_ext':raise ValueError('Unexpected partition')
        entries=[e for e in inv if e['kind']=='file' and e['path']==lib['path']]
        if len(entries)!=1:raise ValueError('Library inventory mismatch')
        prefix=lib['prefix']
        if prefix not in ('hzos','hzos-spaces'):raise ValueError('Unexpected output prefix')
        target=output/(prefix+'.so');dump_entry(image,entries[0],target)
        if target.stat().st_size!=lib['size_bytes'] or digest(target)!=lib['sha256']:raise ValueError('Wrong pinned platform library')
        text,_=command(['readelf','--dyn-syms','-W',str(target)])
        selected=select_symbols(text,lib['exports']);ranges=executable_ranges(target.read_bytes())
        for helper in lib.get('internal_call_targets',[]):
            address=helper['elf_address']
            if not isinstance(address,int) or address%4:raise ValueError('Invalid internal target')
            selected.append({'symbol':helper['name'],'elf_address':address,
                'extent_checked_bytes':4,'selection_basis':'Pinned-library direct callee; not an export or a recovered signature'})
        if len(selected)>24 or len({e['elf_address'] for e in selected})!=len(selected):
            raise ValueError('Duplicate/excessive targets')
        if not all(any(a<=e['elf_address'] and e['elf_address']+e.get('size_bytes',e.get('extent_checked_bytes',0))<=b for a,b in ranges) for e in selected):
            raise ValueError('Non-executable target')
        (output/(prefix+'-functions.txt')).write_text(''.join(f"{e['elf_address']:x}\n" for e in selected))
        (output/(prefix+'-strings.json')).write_text('[]\n')
        rows.append({'library':lib,'selected':selected})
    (output/'shell-platform-native-selection.json').write_text(json.dumps({'modules':rows,
        'executed':False,'private_abi_validated':False},indent=2)+'\n')

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for n in ('images','reconstruction','output'):p.add_argument('--'+n,required=True)
    a=p.parse_args();prepare(a.images,a.reconstruction,a.output)
