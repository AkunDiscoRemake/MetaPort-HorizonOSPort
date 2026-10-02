# SPDX-License-Identifier: GPL-3.0-only
"""Bundle verified ORIGINAL native dependencies for an offline load experiment.

No DEX/resource patches, forged services, Meta signing identity, or runtime claims.
Missing/ambiguous libraries remain explicit. A dependency closure is not a port.
"""
import argparse
from collections import deque
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import zipfile
from horizon.ui.prepare_shell import POLICY
from horizon.ui.prepare_shell_apk import verify_partition
from horizon.ui.loader_audit import PUBLIC_NDK
from handtracking.ai.inspect_original import digest, BUILD
from tools.scan_partitions import command, dump_entry, list_ext4

MAX_LIBRARIES=128
MAX_BYTES=256*1024*1024
APEX_LOCATIONS={
    'libnativehelper.so':('/system/apex/com.android.art.apex','/lib64/libnativehelper.so'),
    'libstatssocket.so':('/system/apex/com.android.os.statsd.apex','/lib64/libstatssocket.so'),
    'libdl_android.so':('/system/apex/com.android.runtime.apex','/lib64/bionic/libdl_android.so'),
}
NAME=re.compile(r'[A-Za-z0-9_][A-Za-z0-9_+.@=\-]{0,180}\.so\Z')


def signatures(name):
    upper=name.upper()
    return upper.startswith('META-INF/') and (upper.endswith(('.SF','.RSA','.DSA','.EC')) or upper=='META-INF/MANIFEST.MF')


def native_needs(path):
    text,_=command(['readelf','-h','-d','-W',str(path)],max_output=2*1024*1024)
    if not re.search(r'Machine:\s+AArch64',text):raise ValueError('Non-ARM64 dependency')
    names=re.findall(r'\(NEEDED\).*?\[(.*?)\]',text)
    if len(names)>128 or any(not NAME.fullmatch(n) or '..' in n for n in names):raise ValueError('Invalid DT_NEEDED')
    return names


def candidate(inventory,name):
    # System libraries of a system_ext app: prefer the system namespace, not
    # vendor variants. This selection is recorded, not a namespace/ABI proof.
    for partition in ('system','system_ext'):
        rows=[e for e in inventory[partition]['entries'] if e['kind']=='file' and
              e['path'] in ('/lib64/'+name,'/system/lib64/'+name)]
        if len(rows)>1:raise ValueError('Ambiguous direct library')
        if rows:return partition,rows[0]
    return None


def member_digest(archive,info):
    h=hashlib.sha256()
    with archive.open(info) as f:
        for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
    return h.hexdigest()


def compare_apks(original,modified,added):
    """Check every retained original member byte-for-byte, not just classes.dex."""
    with zipfile.ZipFile(original) as src,zipfile.ZipFile(modified) as dst:
        originals={i.filename:i for i in src.infolist() if not signatures(i.filename)}
        targets={i.filename:i for i in dst.infolist() if not signatures(i.filename)}
        if len({i.filename for i in dst.infolist()})!=len(dst.infolist()) or set(targets)!=set(originals)|set(added):
            raise ValueError('APK members changed outside declared library additions/signature removal')
        for name,info in originals.items():
            if member_digest(src,info)!=member_digest(dst,targets[name]):raise ValueError('Original member changed: '+name)
        for name,sha in added.items():
            if member_digest(dst,targets[name])!=sha:raise ValueError('Added library hash mismatch')


def prepare(images,reconstruction,original,output,rcpc_compat=False,framework_dex=False):
    images=Path(images);original=Path(original);output=Path(output);output.mkdir(parents=True,exist_ok=True)
    policy=json.loads(POLICY.read_text());recon=json.loads(Path(reconstruction).read_text())
    if digest(original)!=policy['apk_sha256'] or recon['source_zip_sha256']!=policy['ota_sha256']:
        raise ValueError('Unpinned source')
    inventory=json.loads(Path(f'analysis/builds/{BUILD}/static-analysis.json').read_text())['partitions']
    for part in ('system','system_ext'):
        verify_partition(images,part,recon,policy)
    libs=output/'libraries';libs.mkdir(exist_ok=True)
    bundled={}
    with zipfile.ZipFile(original) as z:
        seen=set()
        for info in z.infolist():
            if info.filename in seen:raise ValueError('Duplicate original APK member')
            seen.add(info.filename)
            if not info.filename.startswith('lib/arm64-v8a/') or not info.filename.endswith('.so'):continue
            name=PurePosixPath(info.filename).name
            if not NAME.fullmatch(name) or not 0<info.file_size<=96*1024*1024:raise ValueError('Invalid APK native member')
            p=libs/name
            with z.open(info) as src,p.open('wb') as dst:
                for block in iter(lambda:src.read(1024*1024),b''):dst.write(block)
            bundled[name]=p
    if 'libshell.so' not in bundled or digest(bundled['libshell.so'])!=policy['library_sha256']:
        raise ValueError('Wrong root library')
    # APEX payloads contain dependencies absent from the flat inventory.
    apex_cache={}
    pending=deque(['libshell.so']);visited=set();rows=[];edges=[];added={};unresolved=[];total=0
    while pending:
        name=pending.popleft()
        if name in visited:continue
        if len(visited)>=MAX_LIBRARIES:raise ValueError('Native closure budget')
        visited.add(name)
        if name in PUBLIC_NDK and name not in bundled:
            rows.append({'soname':name,'status':'PUBLIC_NDK_CANDIDATE_NOT_SYMBOL_VERIFIED'});continue
        path=bundled.get(name);origin={'status':'ORIGINAL_APK_MEMBER'}
        if path is None:
            selected=candidate(inventory,name)
            path=libs/name
            if selected:
                part,entry=selected
                if not 0<entry['size_bytes']<=96*1024*1024:raise ValueError('Dependency size budget')
                dump_entry(images/(part+'.img'),entry,path)
                origin={'status':'BUNDLED_ORIGINAL_FIRMWARE_LIBRARY','partition':part,'path':entry['path'],
                        'source_image_sha256':recon['partitions'][part]['sha256']}
            elif name in APEX_LOCATIONS:
                apex_path,member=APEX_LOCATIONS[name]
                if apex_path not in apex_cache:
                    matches=[e for e in inventory['system']['entries'] if e['path']==apex_path and e['kind']=='file']
                    if len(matches)!=1 or matches[0]['size_bytes']>256*1024*1024:raise ValueError('APEX container bounds')
                    container=output/PurePosixPath(apex_path).name
                    dump_entry(images/'system.img',matches[0],container);apex_sha=digest(container)
                    with zipfile.ZipFile(container) as z:
                        payloads=[i for i in z.infolist() if i.filename=='apex_payload.img']
                        if len(payloads)!=1 or payloads[0].file_size>256*1024*1024:raise ValueError('APEX payload budget')
                        apex=container.with_suffix('.img')
                        with z.open(payloads[0]) as src,apex.open('wb') as dst:
                            for block in iter(lambda:src.read(1024*1024),b''):dst.write(block)
                    apex_cache[apex_path]=(apex,list_ext4(apex),apex_sha)
                apex,apex_entries,apex_sha=apex_cache[apex_path]
                matches=[e for e in apex_entries if e['path']==member and e['kind']=='file']
                if len(matches)!=1 or not 0<matches[0]['size_bytes']<=96*1024*1024:
                    raise ValueError('Missing unique bounded APEX library: '+name)
                dump_entry(apex,matches[0],path)
                origin={'status':'BUNDLED_ORIGINAL_APEX_LIBRARY','path':member,'apex_path':apex_path,
                        'apex_sha256':apex_sha,'source_image_sha256':recon['partitions']['system']['sha256']}
            else:
                unresolved.append(name);rows.append({'soname':name,'status':'NOT_RESOLVED_NO_STUB'});continue
            added['lib/arm64-v8a/'+name]=digest(path)
        size=path.stat().st_size;total+=size
        if total>MAX_BYTES:raise ValueError('Native byte budget')
        needs=native_needs(path)
        rows.append({'soname':name,'sha256':digest(path),'size_bytes':size,**origin})
        for child in needs:edges.append({'from':name,'to':child});pending.append(child)
    adaptations=[]
    if rcpc_compat:
        from horizon.ui.rcpc_compat import lower_verified,ADAPTATIONS
        for name,expected_sha,sites in ADAPTATIONS:
            target=libs/name
            adapted,evidence=lower_verified(target.read_bytes(),expected_sha,sites,library=name)
            target.write_bytes(adapted)
            adaptations.append(evidence)
            added['lib/arm64-v8a/'+name]=evidence['adapted_sha256']
            for row in rows:
                if row['soname']==name:
                    row.update(sha256=evidence['adapted_sha256'],source_original_sha256=evidence['source_sha256'],
                               status='FIRMWARE_LIBRARY_WITH_EXPLICIT_RCPC_ADAPTATION')
    dex_members={};framework_evidence=[]
    if framework_dex:
        from horizon.ui.framework_dex import JAR_PATH,JAR_SHA256,additions
        entries=[e for e in inventory['system_ext']['entries'] if e['path']==JAR_PATH and e['kind']=='file']
        if len(entries)!=1 or not 0<entries[0]['size_bytes']<=8*1024*1024:
            raise ValueError('Original framework JAR inventory budget')
        jar=output/'hzos-framework.jar'
        dump_entry(images/'system_ext.img',entries[0],jar)
        if digest(jar)!=JAR_SHA256:raise ValueError('Wrong pinned hzos framework JAR')
        try:
            from horizon.ui.select_framework_classes import select
            dex_members,evidence=additions(original,jar,converter=select)
        except (ValueError,OSError,zipfile.BadZipFile) as error:
            from horizon.ui.framework_dex import read_dexes,REQUIRED
            inspection={'packaging_error':str(error)[:2000],'jars':[],
                        'framework_services_ported':False,'firmware_executed':False}
            # Locate the actual class owner in fixed, verified framework inputs.
            # This diagnostic path never substitutes or packages another JAR.
            for part,source in (('system_ext',JAR_PATH),
                                ('system_ext','/framework/com.oculus.os.platform.jar'),
                                ('system','/system/framework/framework.jar')):
                item={'partition':part,'path':source,'source_image_sha256':recon['partitions'][part]['sha256']}
                try:
                    candidates=[e for e in inventory[part]['entries'] if e['path']==source and e['kind']=='file']
                    if len(candidates)!=1 or not 0<candidates[0]['size_bytes']<=64*1024*1024:
                        raise ValueError('Framework inspection inventory budget')
                    target=output/(part+'-'+PurePosixPath(source).name)
                    dump_entry(images/(part+'.img'),candidates[0],target)
                    entries=read_dexes(target,128*1024*1024,normalize_framework=True)
                    names=set().union(*(entry[3] for entry in entries))
                    item.update(sha256=digest(target),class_definitions=len(names),
                                dex_headers=[dict(member=e[1],**e[4]) for e in entries],
                                defines_required=REQUIRED in names,
                                required_dex_members=[e[1] for e in entries if REQUIRED in e[3]],
                                horizonos_definitions=sum(n.startswith('Lhorizonos/') for n in names),
                                vros_definitions=sum(n.startswith('Lvros/') for n in names))
                except (ValueError,OSError,zipfile.BadZipFile) as inspection_error:
                    item['error']=str(inspection_error)[:2000]
                inspection['jars'].append(item)
            (output/'framework-dex-inspection.json').write_text(json.dumps(inspection,indent=2)+'\n')
            raise
        evidence['source_image_sha256']=recon['partitions']['system_ext']['sha256']
        framework_evidence.append(evidence)
    unsigned=output/'shell-dependencies-unsigned.apk'
    with zipfile.ZipFile(original) as src,zipfile.ZipFile(unsigned,'w') as dst:
        for info in src.infolist():
            if signatures(info.filename):continue
            with src.open(info) as a,dst.open(info,'w') as b:
                for block in iter(lambda:a.read(1024*1024),b''):b.write(block)
        for member in sorted(added):dst.write(libs/PurePosixPath(member).name,member,compress_type=zipfile.ZIP_STORED)
        for member,data in dex_members.items():
            dst.writestr(member,data,compress_type=zipfile.ZIP_STORED)
            added[member]=hashlib.sha256(data).hexdigest()
    compare_apks(original,unsigned,added)
    report={'source_apk_sha256':policy['apk_sha256'],'source_ota_sha256':policy['ota_sha256'],
            'framework_dex_additions':framework_evidence,'instruction_adaptations':adaptations,'original_native_dependencies_unmodified':not adaptations,
            'added_members':added,'nodes':rows,'edges':edges,'unresolved':unresolved,
            'original_members_unchanged':True,'original_signatures_removed':True,
            'namespace_and_symbol_versions_verified':False,'port_ready':False,
            'scope':'Verified-source dependency packaging with explicitly declared instruction adaptations; no service stubs, original DEX/resources unchanged, optional original framework DEX additions'}
    (output/'bundle.json').write_text(json.dumps(report,indent=2)+'\n')
    return report


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('images','reconstruction','original','output'):p.add_argument('--'+name,required=True)
    p.add_argument('--rcpc-compat',action='store_true')
    p.add_argument('--framework-dex',action='store_true')
    a=p.parse_args();prepare(a.images,a.reconstruction,a.original,a.output,a.rcpc_compat,a.framework_dex)
