# SPDX-License-Identifier: GPL-3.0-only
"""Audit captured DT_NEEDED edges; never assume inventory means APK loadability."""
import argparse
import json
from pathlib import Path, PurePosixPath
from collections import deque
from horizon.ui.prepare_shell import POLICY

# Candidates from public Android NDK libraries at the adapter's API 29 floor.
# Symbol/API-version availability, namespaces and ABI still require validation.
PUBLIC_NDK = frozenset(('libandroid.so','liblog.so','libc.so','libm.so','libdl.so',
    'libz.so','libEGL.so','libGLESv2.so','libGLESv3.so','libjnigraphics.so',
    'libnativewindow.so','libmediandk.so','libbinder_ndk.so','libvulkan.so',
    'libOpenSLES.so','libaaudio.so'))


def audit(apk, inventory, platform_libraries=()):
    bundled={}
    for item in apk['native_libraries']:
        member=item['apk_member']
        if not member.startswith('lib/arm64-v8a/'):continue
        name=PurePosixPath(member).name
        if name in bundled:raise ValueError('Duplicate ARM64 member')
        bundled[name]=item
    if 'libshell.so' not in bundled:raise ValueError('No original shell metadata')
    candidates={}
    for partition,data in inventory.items():
        for entry in data.get('entries',[]):
            p=PurePosixPath(entry['path'])
            if entry['kind']=='file' and 'lib64' in p.parts and p.suffix=='.so':
                candidates.setdefault(p.name,[]).append({'partition':partition,'path':str(p)})
    platform={}
    for item in platform_libraries:
        name=PurePosixPath(item['path']).name
        if name in platform:raise ValueError('Ambiguous platform SONAME')
        platform[name]=item
    pending=deque(['libshell.so']);visited=set();nodes=[];edges=[]
    while pending:
        name=pending.popleft()
        if name in visited:continue
        if len(visited)>=128:raise ValueError('Dependency traversal budget exceeded')
        visited.add(name);item=bundled.get(name,platform.get(name))
        if item is not None:
            needs=item.get('needed')
            status=('APK_BUNDLED_CAPTURED_ELF' if name in bundled else 'FIRMWARE_ELF_CAPTURED_NOT_APK_AVAILABLE') if isinstance(needs,list) else 'ELF_METADATA_INCOMPLETE'
            if isinstance(needs,list):
                if len(needs)>128 or any(not isinstance(n,str) or '/' in n for n in needs):
                    raise ValueError('Malformed DT_NEEDED evidence')
                for child in needs:
                    edges.append({'from':name,'to':child})
                    if child not in visited:pending.append(child)
        elif name in PUBLIC_NDK:
            status='PUBLIC_NDK_CANDIDATE_NOT_DEVICE_VERIFIED'
        else:
            status='FIRMWARE_ONLY_CANDIDATE' if name in candidates else 'NOT_LOCATED_IN_CAPTURED_INVENTORY'
        nodes.append({'soname':name,'classification':status,
                      'elf_sha256':item.get('sha256') if item else None,
                      'firmware_candidates':candidates.get(name,[])[:32],
                      'firmware_candidates_truncated':len(candidates.get(name,[]))>32})
    blockers=[n['soname'] for n in nodes if n['classification'] not in
              ('APK_BUNDLED_CAPTURED_ELF','PUBLIC_NDK_CANDIDATE_NOT_DEVICE_VERIFIED')]
    return {'root':'libshell.so','source_apk_sha256':apk['sha256'],
            'scope':'Captured APK and supplied platform ELF edges; uncaptured library dependencies and namespaces remain unresolved',
            'nodes':nodes,'edges':edges,'unresolved_for_unprivileged_apk':blockers,
            'symbol_versions_checked':False,'java_framework_resolved':False,
            'namespace_access_verified':False,'runtime_load_tested':False,'port_ready':False}


def run(source, inventory, output, platform=None):
    r=json.loads(Path(source).read_text());policy=json.loads(POLICY.read_text())
    apk=next(a for a in r['applications'] if a['path']==policy['apk_path'])
    shell=next(n for n in apk['native_libraries'] if n['apk_member']==policy['member'])
    if apk['sha256']!=policy['apk_sha256'] or shell['sha256']!=policy['library_sha256']:
        raise ValueError('Unpinned source evidence')
    platform_data=json.loads(Path(platform).read_text()) if platform else {}
    if platform and (platform_data['source_ota_sha256']!=policy['ota_sha256'] or platform_data['firmware_executed'] is not False):
        raise ValueError('Unexpected platform provenance')
    report=audit(apk,json.loads(Path(inventory).read_text())['partitions'],platform_data.get('libraries',[]))
    from handtracking.ai.inspect_original import digest
    report['source_report_sha256']=digest(source)
    report['platform_report_sha256']=digest(platform) if platform else None
    report['inventory_sha256']=digest(inventory)
    Path(output).write_text(json.dumps(report,indent=2)+'\n')
    return report

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('source','inventory','output'):p.add_argument('--'+name,required=True)
    p.add_argument('--platform')
    a=p.parse_args();run(a.source,a.inventory,a.output,a.platform)
