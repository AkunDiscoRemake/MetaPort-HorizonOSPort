# SPDX-License-Identifier: GPL-3.0-only
"""Inspect original Quest depth resources without executing pickle or inference."""
import argparse
import json
from pathlib import Path
import tempfile
from tools.scan_partitions import dump_entry
from handtracking.ai.inspect_original import model_metadata, digest, BUILD

OTA_SHA256 = 'beea2e092f6239ca21af98466d9b130c22b9ab8822f411b00baf74ebb866858e'
RESOURCES = {
    'system': ['/system/etc/mldepth/stereo_model.ptl', '/system/etc/mldepth/stereo_model_2.ptl'],
    'odm': ['/etc/camera/depthaectuning.json'],
}


def inspect(images, reconstruction, output):
    images=Path(images);output=Path(output);output.parent.mkdir(parents=True,exist_ok=True)
    recon=json.loads(Path(reconstruction).read_text())
    if recon['source_zip_sha256'] != OTA_SHA256: raise ValueError('Wrong OTA')
    policy=json.loads(Path(__file__).with_name('resource-policy.json').read_text())
    pins={(x['partition'],x['path']):x for x in policy['resources']}
    inventory=json.loads(Path(f'analysis/builds/{BUILD}/static-analysis.json').read_text())['partitions']
    report={'build':BUILD,'source_ota_sha256':OTA_SHA256,'models_executed':False,
            'quest_depth_ported':False,'phone_validated':False,'resources':[]}
    for part,paths in RESOURCES.items():
        image=images/(part+'.img');expected=recon['partitions'][part]
        if not expected['sha256_match'] or image.stat().st_size!=expected['size_bytes'] or digest(image)!=expected['sha256']:
            raise ValueError('Wrong partition')
        for path in paths:
            entries=[e for e in inventory[part]['entries'] if e['kind']=='file' and e['path']==path]
            if len(entries)!=1:raise ValueError('Ambiguous/missing original resource')
            with tempfile.TemporaryDirectory() as d:
                original=Path(d)/'resource';dump_entry(image,entries[0],original)
                item={'partition':part,'path':path,'size_bytes':original.stat().st_size,
                      'sha256':digest(original),'partition_sha256':expected['sha256']}
                pin=pins[(part,path)]
                if (item['sha256'],item['size_bytes']) != (pin['sha256'],pin['size_bytes']):
                    raise ValueError('Original depth resource hash mismatch')
                if path.endswith('.ptl'):item['metadata']=model_metadata(original,'.ptl')
                else:
                    if original.stat().st_size>256*1024:raise ValueError('Config size limit')
                    config=json.loads(original.read_text())
                    item['config_root_type']=type(config).__name__
                    item['config_top_level_keys']=sorted(config)[:128] if isinstance(config,dict) else []
                report['resources'].append(item)
                output.write_text(json.dumps(report,indent=2)+'\n')
    return report


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('images','reconstruction','output'):p.add_argument('--'+name,required=True)
    a=p.parse_args();inspect(a.images,a.reconstruction,a.output)
