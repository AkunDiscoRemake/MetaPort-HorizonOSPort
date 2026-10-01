# SPDX-License-Identifier: GPL-3.0-only
"""Extract two hash-pinned small tracking dependency shims; never execute them."""
import json
from pathlib import Path
from handtracking.ai.inspect_original import digest
from tools.scan_partitions import dump_entry

BRIDGES = (
    ('libhzos_trackinghost.meta.so', 'hand-hzos-host', 11072,
     '7a1a81acb7b42c143866c8536768465569109cb316fd26e21115972a1ab2fd28'),
    ('libtrackingvendorutils.so', 'hand-vendor-utils', 10832,
     'a83d12685803d32eae269c7d8b9b168c614fc9dcccefd03b9aa8e3250803afa5'),
)

def prepare_bridges(verified_image, inventory, output):
    """Caller must validate the ODM image against the pinned reconstruction first."""
    output=Path(output);output.mkdir(parents=True,exist_ok=True)
    rows=[]
    for name,prefix,size,sha in BRIDGES:
        path='/lib64/'+name
        entries=[e for e in inventory if e['path']==path and e['kind']=='file']
        if len(entries)!=1: raise ValueError('Bridge inventory mismatch: '+path)
        target=output/name
        dump_entry(verified_image,entries[0],target)
        if target.stat().st_size!=size or digest(target)!=sha:
            raise ValueError('Wrong pinned tracking bridge: '+name)
        rows.append({'path':path,'report_prefix':prefix,'size_bytes':size,'sha256':sha})
    report={'modules':rows,'firmware_executed':False,'private_abi_validated':False}
    (output/'hand-service-bridges.json').write_text(json.dumps(report,indent=2)+'\n')
    return report
