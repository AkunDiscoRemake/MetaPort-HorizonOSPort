# SPDX-License-Identifier: GPL-3.0-only
"""Reserialize selected original SDK classes; compare canonical smali before use."""
import hashlib
import difflib
import itertools
import json
from pathlib import Path
import subprocess
import tempfile
from horizon.ui.framework_dex import definitions,forbidden_boot_definition
from tools.prepare_dex_tools import ROOT,ARTIFACTS


def smali_inventory(root):
    rows={};total=0
    for path in sorted(Path(root).rglob('*.smali')):
        if path.is_symlink():raise ValueError('Symlink disassembly')
        size=path.stat().st_size;total+=size
        if len(rows)>=4096 or size>4*1024*1024 or total>64*1024*1024:
            raise ValueError('Canonical disassembly budget')
        rows[str(path.relative_to(root))]=hashlib.sha256(path.read_bytes()).hexdigest()
    if not rows:raise ValueError('Empty canonical disassembly')
    return rows


def compare_smali(before_root,after_root,expected_count):
    before=smali_inventory(before_root);after=smali_inventory(after_root)
    if before==after and len(before)==expected_count:return before
    changed=sorted(n for n in before.keys() & after.keys() if before[n]!=after[n])
    detail={'expected':expected_count,'before_count':len(before),'after_count':len(after),
            'missing':sorted(before.keys()-after.keys())[:4],
            'added':sorted(after.keys()-before.keys())[:4],'changed_count':len(changed)}
    if changed:
        name=changed[0];detail['first_changed']=name
        a=(Path(before_root)/name).read_text().splitlines()
        b=(Path(after_root)/name).read_text().splitlines()
        detail['diff']='\n'.join(itertools.islice(difflib.unified_diff(a,b,n=2),40))[:1200]
    raise ValueError('Original canonical smali changed or incomplete: '+json.dumps(detail))


STARTUP_CONTRACTS=(
    'oculus/internal/osutils/BinderClient.smali',
    'oculus/internal/osutils/BinderClient$ServiceManagerCallback.smali',
    'com/oculus/os/VrFocusManager.smali',
    'com/oculus/os/ActivityManagerUtils.smali',
    'oculus/internal/IVrFocusService.smali',
    'oculus/internal/IVrTopActivityListener.smali',
    'oculus/internal/IVrFocusListener.smali',
    'oculus/internal/ClientStatus.smali',
    'oculus/internal/ImmersiveApp.smali',
)


def startup_contracts(root,inventory):
    """Bounded original disassembly for adapting the observed service boundary."""
    result=[]
    for name in STARTUP_CONTRACTS:
        if name not in inventory:continue
        path=Path(root)/name
        if path.is_symlink() or path.stat().st_size>96*1024:
            raise ValueError('Startup contract source budget/symlink')
        data=path.read_bytes()
        if hashlib.sha256(data).hexdigest()!=inventory[name]:
            raise ValueError('Changed startup contract disassembly')
        result.append({'class_file':name,'canonical_sha256':inventory[name],
                       'original_smali':data.decode('utf-8'),
                       'scope':'Recovered original third-party code; not a service implementation or GPL relicensing'})
    return result


def select(data):
    original=definitions(data)
    names=sorted(n for n in original if not forbidden_boot_definition(n))
    if not names or len(original)>4096:raise ValueError('Framework class selection budget')
    # Reverify downloaded tools at the point of use, not just at setup time.
    for artifact,sha in ARTIFACTS:
        if hashlib.sha1((ROOT/Path(artifact).name).read_bytes()).hexdigest()!=sha:
            raise ValueError('Changed class-selection tool')
    with tempfile.TemporaryDirectory(prefix='framework-selection-') as d:
        root=Path(d);source=root/'source.dex';output=root/'selected.dex';selection=root/'classes.txt'
        source.write_bytes(data);selection.write_text('\n'.join(names)+'\n')
        with (root/'tool.log').open('w') as log:
            run=subprocess.run(['java','-Xmx1g','-cp',str(ROOT/'classes')+':'+str(ROOT/'*'),
                                'SelectFrameworkClasses',str(source),str(output),str(selection),
                                str(root/'before'),str(root/'after')],stdout=log,stderr=subprocess.STDOUT,timeout=120)
        if run.returncode:
            with (root/'tool.log').open() as log:message=log.read(4000)
            raise ValueError('Framework class selection failed: '+message)
        if not 112<=output.stat().st_size<=32*1024*1024:raise ValueError('Selected DEX budget')
        result=output.read_bytes()
        if definitions(result)!=set(names):raise ValueError('Wrong derived class definitions')
        before=compare_smali(root/'before',root/'after',len(names))
        return result,{'tool':'dexlib2/baksmali 2.5.2','canonical_smali_equal':True,
                       'canonical_inventory_sha256':hashlib.sha256(json.dumps(before,sort_keys=True).encode()).hexdigest(),
                       'startup_contracts':startup_contracts(root/'before',before),
                       'retained_definitions':len(names),'excluded_definitions':sorted(original-set(names)),
                       'instruction_and_data_bytes_unchanged':False,
                       'derived_payload_sha256':hashlib.sha256(result[32:]).hexdigest(),
                       'scope':'Class selection and canonical disassembly equality, not ART or ABI validation'}
