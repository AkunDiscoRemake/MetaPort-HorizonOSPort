# SPDX-License-Identifier: GPL-3.0-only
"""Reserialize selected original SDK classes; compare canonical smali before use."""
import hashlib
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
        before=smali_inventory(root/'before');after=smali_inventory(root/'after')
        if before!=after or len(before)!=len(names):raise ValueError('Original canonical smali changed or incomplete')
        return result,{'tool':'dexlib2/baksmali 2.5.2','canonical_smali_equal':True,
                       'canonical_inventory_sha256':hashlib.sha256(json.dumps(before,sort_keys=True).encode()).hexdigest(),
                       'retained_definitions':len(names),'excluded_definitions':sorted(original-set(names)),
                       'instruction_and_data_bytes_unchanged':False,
                       'derived_payload_sha256':hashlib.sha256(result[32:]).hexdigest(),
                       'scope':'Class selection and canonical disassembly equality, not ART or ABI validation'}
