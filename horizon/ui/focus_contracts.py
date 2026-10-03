# SPDX-License-Identifier: GPL-3.0-only
"""Recover original VR-focus server contracts from already verified partitions.

Never install system-server code or synthesize a replacement service.
"""
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
from horizon.ui.framework_dex import read_dexes
from horizon.ui.select_framework_classes import compare_smali
from tools.prepare_dex_tools import ROOT
from tools.scan_partitions import dump_entry,command

PATHS=(('system_ext','/framework/oculus-system-services.jar'),
       ('system_ext','/framework/horizonos-services.jar'))


def focus_names(names):
    selected=sorted(n for n in names if 'vrfocus' in n.lower())
    if len(selected)>64:raise ValueError('Focus class count budget')
    return selected


def native_contracts(images,inventory,reconstruction,root):
    rows=[]
    for source in ('/bin/vrfocusserver','/etc/init/vrfocusserver.rc','/lib64/libvrfocus_interface-cpp.so'):
        row={'path':source,'partition':'system_ext',
             'source_image_sha256':reconstruction['partitions']['system_ext']['sha256'],
             'executed':False,'packaged_in_apk':False}
        rows.append(row)
        try:
            entries=[e for e in inventory['system_ext']['entries'] if e['path']==source and e['kind']=='file']
            if len(entries)!=1 or not 0<entries[0]['size_bytes']<=1024*1024:
                raise ValueError('Native focus input budget')
            target=root/Path(source).name
            dump_entry(Path(images)/'system_ext.img',entries[0],target)
            data=target.read_bytes();row.update(sha256=hashlib.sha256(data).hexdigest(),size_bytes=len(data))
            if source.endswith('.rc'):
                if len(data)>4096:raise ValueError('Init contract budget')
                row['original_init']=data.decode('utf-8')
            else:
                row['elf_headers'],_=command(['readelf','-h','-d','-n','-W',str(target)],max_output=128*1024)
                row['dynamic_symbols'],_=command(['readelf','--dyn-syms','-W',str(target)],max_output=512*1024)
                row['disassembly'],_=command(['aarch64-linux-gnu-objdump','-d','-C','--no-show-raw-insn',str(target)],max_output=4*1024*1024)
                row['disassembly_complete_for_executable_sections']=True
        except (ValueError,OSError,subprocess.TimeoutExpired) as error:
            row['error']=str(error)[:3000]
    return rows


def collect(images,inventory,reconstruction,output):
    report={'scope':'Original third-party server disassembly, not GPL relicensing or a runnable service',
            'firmware_executed':False,'service_implemented':False,'jars':[]}
    remaining=1024*1024
    with tempfile.TemporaryDirectory(prefix='focus-server-contracts-') as d:
        root=Path(d)
        report['native_contracts']=native_contracts(images,inventory,reconstruction,root)
        for part,source in PATHS:
            row={'partition':part,'path':source,'source_image_sha256':reconstruction['partitions'][part]['sha256']}
            report['jars'].append(row)
            try:
                entries=[e for e in inventory[part]['entries'] if e['path']==source and e['kind']=='file']
                if len(entries)!=1 or not 0<entries[0]['size_bytes']<=32*1024*1024:
                    raise ValueError('Focus JAR inventory budget')
                jar=root/Path(source).name;dump_entry(Path(images)/(part+'.img'),entries[0],jar)
                row['sha256']=hashlib.sha256(jar.read_bytes()).hexdigest();row['contracts']=[]
                for index,member,data,names,header in read_dexes(jar,64*1024*1024,normalize_framework=True):
                    selected=focus_names(names)
                    if not selected:continue
                    stage=root/(jar.stem+'-'+str(index));stage.mkdir()
                    dex=stage/'input.dex';dex.write_bytes(data)
                    selection=stage/'names.txt';selection.write_text('\n'.join(selected)+'\n')
                    run=subprocess.run(['java','-Xmx1g','-cp',str(ROOT/'classes')+':'+str(ROOT/'*'),
                        'SelectFrameworkClasses',str(dex),str(stage/'temporary-analysis-only.dex'),str(selection),
                        str(stage/'before'),str(stage/'after')],capture_output=True,text=True,timeout=120)
                    if run.returncode:raise ValueError('Focus disassembly failed: '+run.stderr[-2000:])
                    canonical=compare_smali(stage/'before',stage/'after',len(selected))
                    for name,sha in canonical.items():
                        file=stage/'before'/name;size=file.stat().st_size
                        item={'class_file':name,'source_member':member,'canonical_sha256':sha}
                        if size<=384*1024 and size<=remaining:
                            item['original_smali']=file.read_text();remaining-=size
                        else:item['omitted']='SOURCE_TEXT_BUDGET'
                        row['contracts'].append(item)
            except (ValueError,OSError,subprocess.TimeoutExpired) as error:
                row['error']=str(error)[:3000]
    Path(output).write_text(json.dumps(report,indent=2)+'\n')
    return report
