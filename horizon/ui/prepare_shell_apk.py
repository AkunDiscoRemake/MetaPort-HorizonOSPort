# SPDX-License-Identifier: GPL-3.0-only
"""Extract the unmodified, hash-pinned original APK for isolated baseline testing."""
import argparse
import json
from pathlib import Path
from horizon.ui.prepare_shell import POLICY
from handtracking.ai.inspect_original import digest, BUILD
from tools.scan_partitions import dump_entry


def prepare(images, reconstruction, output):
    policy=json.loads(POLICY.read_text());recon=json.loads(Path(reconstruction).read_text())
    if recon['source_zip_sha256']!=policy['ota_sha256']:raise ValueError('Wrong OTA')
    image=Path(images)/'system_ext.img';part=recon['partitions']['system_ext']
    if not part['sha256_match'] or image.stat().st_size!=part['size_bytes'] or digest(image)!=part['sha256']:
        raise ValueError('Wrong system_ext image')
    inventory=json.loads(Path(f'analysis/builds/{BUILD}/static-analysis.json').read_text())
    entries=[e for e in inventory['partitions']['system_ext']['entries']
             if e['path']==policy['apk_path'] and e['kind']=='file']
    if len(entries)!=1 or not 0<entries[0]['size_bytes']<=512*1024*1024:
        raise ValueError('APK inventory bounds')
    output=Path(output);output.parent.mkdir(parents=True,exist_ok=True)
    dump_entry(image,entries[0],output)
    if digest(output)!=policy['apk_sha256']:
        output.unlink();raise ValueError('Wrong APK hash')


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('images','reconstruction','output'):p.add_argument('--'+name,required=True)
    a=p.parse_args();prepare(a.images,a.reconstruction,a.output)
