# SPDX-License-Identifier: GPL-3.0-only
"""Append original framework DEX, never manufacture missing classes/services.

The caller must verify the source partition before extracting the fixed JAR.
DEX checks here establish bounded metadata/provenance, not full ART verification.
"""
import hashlib
import re
import struct
import zlib
import zipfile
from horizon.ui.dex_contract import Dex

JAR_PATH='/framework/hzos-framework.jar'
JAR_SHA256='b1c5111bb301daf971b658414daf8e43a0b4cdac9ecc2e94a554d0c861607e42'
REQUIRED='Lhorizonos/graphics/Vector4f;'


def definitions(data):
    dex=Dex(data);names=set()
    for i in range(dex.tables['classes'][0]):
        name=dex.type(dex.u32(dex.entry('classes',i)))
        if not name.startswith('L') or not name.endswith(';') or name in names:
            raise ValueError('Invalid or duplicate DEX class definition')
        names.add(name)
    return names


def normalized_framework_header(data):
    if len(data)<112:raise ValueError('Truncated framework DEX')
    result=bytearray(data)
    result[12:32]=hashlib.sha1(result[32:]).digest()
    struct.pack_into('<I',result,8,zlib.adler32(result[12:])&0xffffffff)
    result=bytes(result)
    return result,{'source_dex_sha256':hashlib.sha256(data).hexdigest(),
                   'source_checksum_hex':data[8:12].hex(),'source_signature_hex':data[12:32].hex(),
                   'header_checksums_recomputed':result!=data,
                   'payload_sha256':hashlib.sha256(data[32:]).hexdigest(),
                   'changed_byte_range':[8,32] if result!=data else None,
                   'instruction_and_data_bytes_unchanged':True}


def read_dexes(path,byte_limit,normalize_framework=False):
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
            evidence={}
            if normalize_framework:data,evidence=normalized_framework_header(data)
            rows.append((index,info.filename,data,definitions(data),evidence))
    if not rows:raise ValueError('No standard DEX in archive')
    return sorted(rows)


def forbidden_boot_definition(name):
    # This is Meta's additional registry class, NOT android.app.SystemServiceRegistry.
    # Merely carrying it cannot register services or grant its caller privileges.
    root='Landroid/app/VrosSystemServiceRegistry'
    if name==root+';' or name.startswith(root+'$'):return False
    return name.startswith(('Landroid/','Ljava/','Ljavax/','Ldalvik/','Lsun/'))


def additions(original,jar):
    """Keep framework code/data unchanged, normalizing only header checksums; reject collisions."""
    originals=read_dexes(original,256*1024*1024)
    framework=read_dexes(jar,32*1024*1024,normalize_framework=True)
    existing=set().union(*(r[3] for r in originals));new=set()
    for _,_,_,names,_ in framework:
        if names & (existing|new):raise ValueError('Framework class collides with existing DEX: '+', '.join(sorted(names & (existing|new))[:8]))
        if any(forbidden_boot_definition(n) for n in names):
            raise ValueError('Refusing framework DEX containing boot namespace definitions: '+', '.join(sorted(n for n in names if forbidden_boot_definition(n))[:8]))
        new.update(names)
    if REQUIRED not in new:raise ValueError('Original Vector4f definition not found in selected JAR')
    base=max(r[0] for r in originals);members={};evidence=[]
    if base+len(framework)>128:raise ValueError('Combined DEX index budget')
    for offset,(_,source,data,names,metadata) in enumerate(framework,1):
        target=f'classes{base+offset}.dex';members[target]=data
        evidence.append({'source_member':source,'apk_member':target,
                         'sha256':hashlib.sha256(data).hexdigest(),'size_bytes':len(data),
                         'class_definitions':len(names),**metadata})
    return members,{'source_path':JAR_PATH,'source_jar_sha256':hashlib.sha256(jar.read_bytes()).hexdigest(),
                    'members':evidence,'required_definition':REQUIRED,
                    'original_dex_members_unchanged':True,'framework_services_ported':False,
                    'framework_registry_registration_performed':False,
                    'scope':'Original framework code/data with explicit header checksum normalization; not system service registration'}
