# SPDX-License-Identifier: GPL-3.0-only
"""Inspect original storage/Keystore startup dependencies; never supply fake keys.

Read-only host analysis of fixed-build, hash-verified images. Does not execute init
commands, HALs, authentication, key-generation or secure-world operations.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import stat
import tempfile
from tools.scan_partitions import command,dump_entry,elf_report

BUILD='52168470052900520'
CONFIGS={
    'system':{'/system/etc/init/hw/init.rc','/system/etc/init/keystore2.rc',
              '/system/etc/init/atrace.rc','/system/etc/init/perfetto.rc',
              '/system/etc/init/oculus.perfetto.rc',
              '/system/etc/init/vold.rc','/system/etc/init/gatekeeperd.rc',
              '/system/etc/vintf/manifest/android.system.keystore2-service.xml'},
    'vendor':{'/bin/init.insmod.sh','/etc/init/android.hardware.security.keymint-service-qti.rc',
              '/etc/init/android.hardware.gatekeeper@1.0-service-qti.rc',
              '/etc/init/qseecomd.rc','/etc/init/vendor.qti.hardware.qseecom@1.0-service.rc',
              '/etc/vintf/manifest/android.hardware.security.keymint-service-qti.xml'},
}
BINARIES={
    'system':{'/system/bin/keystore2','/system/bin/vold','/system/lib64/libkeystore2_crypto.so',
              '/system/lib64/libkeymint.so','/system/lib64/libkeymaster4support.so'},
    'vendor':{'/bin/hw/android.hardware.security.keymint-service-qti','/bin/qseecomd',
              '/bin/hw/vendor.qti.hardware.qseecom@1.0-service','/lib64/libQSEEComAPI.so',
              '/lib64/libqtikeymint.so','/lib64/libkeymasterdeviceutils.so',
              '/lib64/hw/vendor.qti.hardware.qseecom@1.0-impl.so'},
}
INTEREST=re.compile(r'keystore|keymint|keymaster|qsee|secureclock|sharedsecret|wrappedkey|/metadata|/data/misc|/dev/|/firmware|KeyMintDevice',re.I)


def digest(path):
    h=hashlib.sha256()
    with path.open('rb') as stream:
        while data:=stream.read(1024*1024):h.update(data)
    return h.hexdigest()


def parse_init(text):
    """Record declarations, not a full Android init interpreter or startup proof.

    Keep arguments/commands as text: do not apply shell expansion, execute imports,
    resolve properties or reinterpret quoted values with an unrelated shell parser.
    """
    if len(text.encode('utf-8'))>256*1024:raise ValueError('Init text size limit')
    lines=text.splitlines()
    if len(lines)>8192:raise ValueError('Init line limit')
    result={'services':[],'actions':[],'imports':[],'unclassified':[],
            'commands_executed':False,'complete_init_grammar':False}
    current=None;pending='';start=0
    for number,line in enumerate(lines,1):
        if len(line)>8192:raise ValueError('Init line length limit')
        if not pending:start=number
        pending+=line
        trailing=len(pending)-len(pending.rstrip('\\'))
        if trailing%2:
            pending=pending[:-1]+' '
            if len(pending)>8192:raise ValueError('Continued init line limit')
            continue
        clean=pending.strip();pending=''
        if not clean or clean.startswith('#'):continue
        if clean.startswith('service '):
            fields=clean.split(None,2)
            if len(fields)!=3:raise ValueError('Incomplete service declaration')
            current={'name':fields[1],'command_line':fields[2],'line':start,'options':[]}
            result['services'].append(current)
        elif clean.startswith('on '):
            current={'trigger':clean[3:],'line':start,'commands':[]}
            result['actions'].append(current)
        elif clean.startswith('import '):
            result['imports'].append({'expression':clean[7:],'line':start})
            current=None
        elif current is not None:
            current['options' if 'name' in current else 'commands'].append(clean)
        else:result['unclassified'].append({'line':start,'text':clean})
    if pending:raise ValueError('Unterminated init continuation')
    return result


def select(entries,paths):
    selected={}
    for entry in entries:
        if entry['kind']=='file' and entry['path'] in paths:
            if entry['path'] in selected:raise ValueError('Duplicate inventory path')
            selected[entry['path']]=entry
    if set(selected)!=paths:raise ValueError('Missing security contract inventory path')
    return selected


def inspect(images,reconstruction,output):
    inventory=json.loads(Path(f'analysis/builds/{BUILD}/static-analysis.json').read_text())['partitions']
    verified=json.loads(reconstruction.read_text())['partitions']
    result={'build':BUILD,'firmware_executed_by_inspector':False,'keys_generated':False,
            'keymint_implemented':False,'secure_world_emulated':False,'configuration':[],
            'binaries':[],'verified_images':{},'qualification':'STATIC_CONTRACT_NOT_RUNTIME_VALIDATED'}
    for partition in ('system','vendor'):
        image=images/(partition+'.img');expected=verified[partition]
        if not stat.S_ISREG(image.lstat().st_mode):raise ValueError('Expected regular image')
        if not expected['sha256_match'] or image.stat().st_size!=expected['size_bytes']:
            raise ValueError('Unverified image size/status')
        actual=digest(image)
        if actual!=expected['sha256']:raise ValueError('Image digest mismatch')
        result['verified_images'][partition]=actual
        selected=select(inventory[partition]['entries'],CONFIGS[partition]|BINARIES[partition])
        for path,entry in sorted(selected.items()):
            if path in CONFIGS[partition] and not 0<entry['size_bytes']<=256*1024:
                raise ValueError('Security config size limit')
            with tempfile.TemporaryDirectory() as folder:
                binary=Path(folder)/'component';dump_entry(image,entry,binary)
                raw=binary.read_bytes()
                row={'partition':partition,'path':path,'sha256':hashlib.sha256(raw).hexdigest(),'size_bytes':len(raw)}
                if path in CONFIGS[partition]:
                    text=raw.decode('utf-8');row['text']=text
                    if path.endswith('.rc'):row['declarations']=parse_init(text)
                    result['configuration'].append(row)
                else:
                    elf=elf_report(binary,deep=False)
                    if elf['format']!='ELF':raise ValueError('Expected security ELF')
                    row['elf']=elf
                    row['diagnostic_strings']=sorted({m.group().decode('ascii') for m in
                        re.finditer(rb'[ -~]{5,512}',raw) if INTEREST.search(m.group().decode('ascii'))})[:256]
                    # The generic ELF helper samples symbols. Search the full bounded
                    # dynsym output for this contract instead of inferring absence.
                    symbols,_=command(['readelf','--dyn-syms','-W',str(binary)],max_output=16*1024*1024)
                    row['security_symbols_sample']=[line.strip() for line in symbols.splitlines() if INTEREST.search(line)][:256]
                    result['binaries'].append(row)
    output.write_text(json.dumps(result,indent=2)+'\n')
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('images','reconstruction','output'):p.add_argument('--'+name,required=True,type=Path)
    a=p.parse_args();inspect(a.images,a.reconstruction,a.output)
