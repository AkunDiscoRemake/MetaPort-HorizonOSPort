# SPDX-License-Identifier: GPL-3.0-only
"""Append original framework DEX, never manufacture missing classes/services.

The caller must verify the source partition before extracting the fixed JAR.
DEX checks here establish bounded metadata/provenance, not full ART verification.
"""
import hashlib
import re
import zipfile
from horizon.ui.dex_contract import Dex

JAR_PATH='/framework/hzos-framework.jar'
REQUIRED='Lhorizonos/graphics/Vector4f;'


def definitions(data):
    dex=Dex(data);names=set()
    for i in range(dex.tables['classes'][0]):
        name=dex.type(dex.u32(dex.entry('classes',i)))
        if not name.startswith('L') or not name.endswith(';') or name in names:
            raise ValueError('Invalid or duplicate DEX class definition')
        names.add(name)
    return names


def read_dexes(path,byte_limit):
    rows=[];total=0
    with zipfile.ZipFile(path) as archive:
        infos=archive.infolist()
        if len(infos)>100000 or len({i.filename for i in infos})!=len(infos):
            raise ValueError('Duplicate/over-budget archive members')
        for info in infos:
            match=re.fullmatch(r'classes(\d*)\.dex',info.filename)
            if not match:continue
            index=int(match[1]) if match[1] else 1
            if match[1] and (index<2 or str(index)!=match[1]):raise ValueError('Noncanonical DEX name')
            total+=info.file_size
            if index>128 or len(rows)>=32 or not 112<=info.file_size<=128*1024*1024 or total>byte_limit:
                raise ValueError('DEX archive budget')
            data=archive.read(info)
            rows.append((index,info.filename,data,definitions(data)))
    if not rows:raise ValueError('No standard DEX in archive')
    return sorted(rows)


def additions(original,jar):
    """Return byte-identical additional DEX members; reject class/boot collisions."""
    originals=read_dexes(original,256*1024*1024)
    framework=read_dexes(jar,32*1024*1024)
    existing=set().union(*(r[3] for r in originals));new=set()
    for _,_,_,names in framework:
        if names & (existing|new):raise ValueError('Framework class collides with existing DEX')
        if any(n.startswith(('Landroid/','Ljava/','Ljavax/','Ldalvik/','Lsun/')) for n in names):
            raise ValueError('Refusing framework DEX containing boot namespace definitions')
        new.update(names)
    if REQUIRED not in new:raise ValueError('Original Vector4f definition not found in selected JAR')
    base=max(r[0] for r in originals);members={};evidence=[]
    if base+len(framework)>128:raise ValueError('Combined DEX index budget')
    for offset,(_,source,data,names) in enumerate(framework,1):
        target=f'classes{base+offset}.dex';members[target]=data
        evidence.append({'source_member':source,'apk_member':target,
                         'sha256':hashlib.sha256(data).hexdigest(),'size_bytes':len(data),
                         'class_definitions':len(names)})
    return members,{'source_path':JAR_PATH,'source_jar_sha256':hashlib.sha256(jar.read_bytes()).hexdigest(),
                    'members':evidence,'required_definition':REQUIRED,
                    'original_dex_members_unchanged':True,'framework_services_ported':False,
                    'scope':'Byte-identical original framework DEX addition, not system service registration'}
