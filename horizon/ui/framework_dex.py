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
FRAMEWORK_INPUTS=((JAR_PATH,JAR_SHA256,REQUIRED),
    ('/framework/com.oculus.os.platform.jar',
     '9659b2f81dd6ba59c4ea549e0229717e2a22e6cc31369b5735ddc4b90d495285',
     'Lcom/oculus/os/ActivityManagerUtils;'))


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
    return name.startswith(('Landroid/','Ljava/','Ljavax/','Ldalvik/','Lsun/','Lcom/android/','Lorg/xml/','Lorg/w3c/'))


def additions(original,jar,converter=None,*,prior_members=None,source_path=JAR_PATH,required=REQUIRED):
    """Add selected original framework classes; never replace existing APK definitions."""
    originals=read_dexes(original,256*1024*1024)
    framework=read_dexes(jar,32*1024*1024,normalize_framework=True)
    prior_members=prior_members or {}
    prior_names=set()
    prior_indices=[]
    for member,data in prior_members.items():
        match=re.fullmatch(r'classes([2-9]|[1-9][0-9]+)\.dex',member)
        if not match:raise ValueError('Invalid prior DEX member')
        names=definitions(data)
        if names & prior_names:raise ValueError('Duplicate prior DEX definitions')
        prior_names.update(names);prior_indices.append(int(match[1]))
    selected=[]
    for index,source,data,names,metadata in framework:
        if any(forbidden_boot_definition(n) for n in names) and converter is not None:
            result,proof=converter(data)
            expected={n for n in names if not forbidden_boot_definition(n)}
            if definitions(result)!=expected or proof.get('canonical_smali_equal') is not True:
                raise ValueError('Unverified framework class selection')
            data=result;names=expected;metadata={**metadata,**proof}
        selected.append((index,source,data,names,metadata))
    framework=selected
    existing=set().union(*(r[3] for r in originals))
    if existing & prior_names or set(prior_indices) & {r[0] for r in originals}:
        raise ValueError('Prior DEX collides with original APK')
    existing.update(prior_names);new=set()
    for _,_,_,names,_ in framework:
        if names & (existing|new):raise ValueError('Framework class collides with existing DEX: '+', '.join(sorted(names & (existing|new))[:8]))
        if any(forbidden_boot_definition(n) for n in names):
            raise ValueError('Refusing framework DEX containing boot namespace definitions: '+', '.join(sorted(n for n in names if forbidden_boot_definition(n))[:8]))
        new.update(names)
    if required not in new:raise ValueError('Required original definition not found in selected JAR: '+required)
    base=max([r[0] for r in originals]+prior_indices);members={};evidence=[]
    if base+len(framework)>128:raise ValueError('Combined DEX index budget')
    for offset,(_,source,data,names,metadata) in enumerate(framework,1):
        target=f'classes{base+offset}.dex';members[target]=data
        evidence.append({'source_member':source,'apk_member':target,
                         'sha256':hashlib.sha256(data).hexdigest(),'size_bytes':len(data),
                         'class_definitions':len(names),**metadata})
    return members,{'source_path':source_path,'source_jar_sha256':hashlib.sha256(jar.read_bytes()).hexdigest(),
                    'members':evidence,'required_definition':required,
                    'original_dex_members_unchanged':True,'framework_services_ported':False,
                    'framework_registry_registration_performed':False,
                    'scope':'Original framework classes with explicit header normalization or canonical-smali-checked class selection; not service registration'}
