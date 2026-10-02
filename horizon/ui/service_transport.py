# SPDX-License-Identifier: GPL-3.0-only
"""Explicit app-local Binder discovery adaptation, not a VR focus implementation."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
from horizon.ui.framework_dex import definitions
from horizon.ui.select_framework_classes import smali_inventory
from tools.prepare_dex_tools import ROOT

OWNERS=('oculus/internal/osutils/BinderClient.smali',
        'oculus/internal/osutils/BinderClient$ServiceManagerCallback.smali')
TYPES={'Landroid/os/IServiceCallback;':'Lorg/metaport/port/services/ServiceCallback;',
       'Landroid/os/IServiceCallback$Stub;':'Lorg/metaport/port/services/ServiceCallback$Stub;',
       'Landroid/os/ServiceManager;':'Lorg/metaport/port/services/ServiceDirectory;'}
# Captured from SHA-pinned firmware, before any transport adaptation.
CONTRACT_HASHES={'oculus/internal/osutils/BinderClient.smali': 'ca948a01272ea89f5cb5a84a0c35b25e890e97bc23546ecdea68e83f17eaf067', 'oculus/internal/osutils/BinderClient$ServiceManagerCallback.smali': '417b24ca2a76b4c7eb6e8abeb1b0f1d35850cf9de09bd6bb4c8eae7cb7bb19f8'}


def verify_transport(before,after):
    a=smali_inventory(before);b=smali_inventory(after)
    if a.keys()!=b.keys():raise ValueError('Transport changed class inventory')
    changed=[]
    for name,sha in a.items():
        if name not in OWNERS:
            if sha!=b[name]:raise ValueError('Unexpected transport change: '+name)
            continue
        if sha!=CONTRACT_HASHES.get(name):raise ValueError('Unrecognized original transport contract: '+name)
        text=(Path(before)/name).read_text()
        for old,new in TYPES.items():text=text.replace(old,new)
        if text==(Path(before)/name).read_text() or text!=(Path(after)/name).read_text():
            raise ValueError('Unexpected transport instructions or metadata: '+name)
        changed.append(name)
    if set(changed)!=set(OWNERS):raise ValueError('Missing transport contract')
    return changed


def adapt(data):
    with tempfile.TemporaryDirectory(prefix='service-transport-') as d:
        root=Path(d);src=root/'source.dex';out=root/'adapted.dex';src.write_bytes(data)
        run=subprocess.run(['java','-Xmx1g','-cp',str(ROOT/'classes')+':'+str(ROOT/'*'),
            'AdaptServiceTransport',str(src),str(out),str(root/'before'),str(root/'after')],
            capture_output=True,text=True,timeout=120)
        if run.returncode:raise ValueError('Service transport adaptation failed: '+run.stderr[-4000:])
        if not 112<=out.stat().st_size<=32*1024*1024:raise ValueError('Adapted DEX budget')
        result=out.read_bytes()
        if definitions(data)!=definitions(result):raise ValueError('Transport changed definitions')
        changed=verify_transport(root/'before',root/'after')
        return result,{'source_sha256':hashlib.sha256(data).hexdigest(),
            'adapted_sha256':hashlib.sha256(result).hexdigest(),'changed_classes':changed,
            'descriptor_mapping':TYPES,'exact_declared_changes_verified':True,
            'original_firmware_code_unmodified':False,'system_service_access_granted':False,
            'vrfocus_service_implemented':False,'scope':'App-local service discovery only; missing providers remain unavailable'}


def adapter_dex():
    sdk=Path(os.environ['ANDROID_HOME']);android=sdk/'platforms/android-35/android.jar'
    sources=sorted(Path('port/android/adapters/src/main/java/org/metaport/port/services').glob('*.java'))
    if {p.name for p in sources}!={'ServiceCallback.java','ServiceDirectory.java'}:
        raise ValueError('Unexpected transport adapter source set')
    with tempfile.TemporaryDirectory(prefix='service-adapter-') as d:
        root=Path(d);classes=root/'classes';classes.mkdir();out=root/'dex';out.mkdir()
        subprocess.run(['javac','--release','8','-classpath',str(android),'-d',str(classes),
            *map(str,sources)],check=True,timeout=60,capture_output=True)
        subprocess.run([str(sdk/'build-tools/35.0.0/d8'),'--min-api','29','--lib',str(android),
            '--output',str(out),*map(str,sorted(classes.rglob('*.class')))],check=True,timeout=60,capture_output=True)
        if {p.name for p in out.iterdir()}!={'classes.dex'}:raise ValueError('Adapter DEX output set')
        data=(out/'classes.dex').read_bytes();names=definitions(data)
        if not names or any(not n.startswith('Lorg/metaport/port/services/') for n in names):
            raise ValueError('Unexpected adapter definitions')
        return data,{'source_files':{str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in sources},
                     'sha256':hashlib.sha256(data).hexdigest(),'class_definitions':sorted(names),
                     'scope':'Project-original local Binder transport, no service providers or firmware substitutes'}
