# SPDX-License-Identifier: GPL-3.0-only
"""Fail closed on drift in the pinned evidence used by the owned Binder codec.

This checks recovered evidence, not execution against Meta's original proxy.
"""
import hashlib
import json
from pathlib import Path
import re

ROOT=Path(__file__).resolve().parents[2]
METHODS=(
    'getClientFocusStatus(I[I)[Loculus/internal/ClientStatus;',
    'registerVrFocusListener(Loculus/internal/IVrFocusListener;I)Z',
    'unregisterVrFocusListener(I)Z',
    'registerVrTopActivityListener(Loculus/internal/IVrTopActivityListener;)Z',
    'unregisterVrTopActivityListener()Z', 'setAppState(II)V',
    'getImmersiveApp()Loculus/internal/ImmersiveApp;', 'getTopActivity()Ljava/lang/String;',
    'getForegroundApps()[Ljava/lang/String;', 'grantTrackingServiceAccess(I)V',
    'revokeTrackingServiceAccess(I)V')
SMALI_HASHES={
    'IVrFocusService':'ba3829a030da8d1ef2f317d073350a5c743e7eab7b499ba5f448aafcca99b8ec',
    'IVrFocusListener':'57ec8d3ae1ef32605057aaf9741782ccbda2364a07ef4922b58da888eb2e45e9',
    'IVrTopActivityListener':'b92a8dd16362980d966f747bdcb3731f16723901c76e316dcf7036d5ed57ecc5',
    'ClientStatus':'f43f41dba86d98e238b0990dfd217e41e878198b3dfdb6ee42d857181e9a44a7',
    'ImmersiveApp':'1526597451eeadceab7a281a977a7aa29e81f706c8ad158b9d42c4f8884a9848'}
C_HASHES={
    0x8130:'ab50e2756e5e38d24226b09bc2ed3ddda896a10f850b798a8fd1bebd744408cf',
    0x8610:'f868f77dddfc62276c158878b4a40a92165fda909a776da8fbea41585811558b',
    0xaa00:'2ffb29c75616edb2e6521d03797ddfd24847d7ca58c782363234e5ae86d854a5',
    0xc070:'d4e99eefa1d144064440076d3095f44da08dbd8de1c45accf05281728b1770c2',
    0xc9c0:'b84207971c18124fb57d65d522fb62d11c88a3d0fedf5be79dc1875563db94bf'}

def sha(text): return hashlib.sha256(text.encode()).hexdigest()

def verify(java_report,native_report):
    contracts={}
    for addition in java_report['framework_dex_additions']:
        for member in addition.get('members',[]):
            for item in member.get('startup_contracts',[]):
                name=item['class_file']
                if name.startswith('oculus/internal/') and name.endswith('.smali'):
                    short=name[len('oculus/internal/'):-6]
                    if short in SMALI_HASHES:
                        if short in contracts:raise ValueError('Duplicate focus contract')
                        contracts[short]=item['original_smali']
    if set(contracts)!=set(SMALI_HASHES):raise ValueError('Missing focus contracts')
    for name,text in contracts.items():
        if sha(text)!=SMALI_HASHES[name]:raise ValueError('Focus smali drift: '+name)
    methods=re.findall(r'^\.method public abstract blacklist (\S+)',contracts['IVrFocusService'],re.M)
    if set(methods)!=set(METHODS) or len(methods)!=11:raise ValueError('Focus method drift')
    fields={}
    for name,expected in (('ClientStatus',['pid','hasFocus']),('ImmersiveApp',['packageName','pid','uid','isTopActivity'])):
        writer=contracts[name].split('writeToParcel(Landroid/os/Parcel;I)V',1)[1].split('.end method',1)[0]
        actual=re.findall(r'iget(?:-object|-boolean)? .*?;->(\w+):',writer)
        if actual!=expected:raise ValueError('Focus parcel field order drift')
        fields[name]=actual
    if native_report['program_sha256']!='949bebe7639f07ec86c818456a41c403e6a946ed9073b162b3d46ee29291916c':
        raise ValueError('Wrong native focus interface')
    functions={f['elf_address']:f['c'] for f in native_report['functions']}
    for offset,expected in C_HASHES.items():
        if offset not in functions or sha(functions[offset])!=expected:raise ValueError('Native focus function drift')
    dispatch=functions[0xaa00]
    rows=[]
    for code,signature in enumerate(METHODS,1):
        label='0xb' if code==11 else str(code)
        body=dispatch.split('case '+label+':',1)[1].split('\n  case ',1)[0]
        name=signature.split('(')[0]
        if 'IVrFocusService::'+name+'::cppServer' not in body:raise ValueError('Transaction ID drift')
        rows.append({'transaction':code,'signature':signature})
    return {'transactions':rows,'parcel_fields':fields,'original_proxy_executed':False,
            'service_published':False,'scope':'Pinned static wire evidence only'}

def load():
    return (json.loads((ROOT/'analysis/android-runtime/original-shell-rcpc-dependency-bundle.json').read_text()),
            json.loads((ROOT/'analysis/builds/52168470052900520/focus-native-interface.json').read_text()))

if __name__=='__main__':print(json.dumps(verify(*load()),indent=2))
