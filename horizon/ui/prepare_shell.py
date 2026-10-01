# SPDX-License-Identifier: GPL-3.0-only
"""Extract pinned VrShell native entry points. Never load the APK or library."""
import argparse
import json
from pathlib import Path
import struct
import tempfile
import zipfile
from handtracking.ai.inspect_original import digest, BUILD
from tools.scan_partitions import dump_entry, command

PREFIX='Java_com_oculus_vrshell_ShellApplication_'
TARGETS=['JNI_OnLoad']+[PREFIX+x for x in ('nativeInit','nativeOnDestroy','nativeFrameCommand',
    'nativePassthroughRequest','nativeOnSizeChanged','nativeOnLaunchContextReady')]
POLICY=Path(__file__).with_name('shell-policy.json')


def select_symbols(text):
    found={}
    for line in text.splitlines():
        cols=line.split()
        if len(cols)!=8 or not cols[0].endswith(':') or cols[7] not in TARGETS:
            continue
        if cols[3]!='FUNC' or cols[4] not in ('GLOBAL','WEAK') or cols[6]=='UND':
            continue
        address=int(cols[1],16);size=int(cols[2],0)
        if address<=0 or size<=0:raise ValueError('Invalid entry point')
        if cols[7] in found:raise ValueError('Duplicate export')
        found[cols[7]]={'symbol':cols[7],'elf_address':address,'size_bytes':size}
    if set(found)!=set(TARGETS):raise ValueError('Missing required original exports')
    return [found[name] for name in TARGETS]


def executable_ranges(blob):
    if len(blob)<64 or blob[:6]!=b'\x7fELF\x02\x01' or struct.unpack_from('<HH',blob,16)!=(3,183):
        raise ValueError('Expected little-endian ARM64 ET_DYN')
    offset=struct.unpack_from('<Q',blob,32)[0]
    size,count=struct.unpack_from('<HH',blob,54)
    if size!=56 or not 0<count<=256 or offset+size*count>len(blob):raise ValueError('Invalid program headers')
    ranges=[]
    for i in range(count):
        typ,flags,off,va,_,filesz,memsz,_=struct.unpack_from('<IIQQQQQQ',blob,offset+i*size)
        if typ==1 and flags&1:
            if filesz>memsz or off+filesz>len(blob):raise ValueError('Invalid executable segment')
            ranges.append((va,va+filesz))
    return ranges


def prepare(images,reconstruction,output):
    output=Path(output);output.mkdir(parents=True,exist_ok=True)
    policy=json.loads(POLICY.read_text());recon=json.loads(Path(reconstruction).read_text())
    if recon['source_zip_sha256']!=policy['ota_sha256']:raise ValueError('Wrong OTA')
    image=Path(images)/'system_ext.img';p=recon['partitions']['system_ext']
    if not p['sha256_match'] or image.stat().st_size!=p['size_bytes'] or digest(image)!=p['sha256']:
        raise ValueError('Wrong system_ext image')
    inv=json.loads(Path(f'analysis/builds/{BUILD}/static-analysis.json').read_text())['partitions']['system_ext']['entries']
    entries=[e for e in inv if e['path']==policy['apk_path'] and e['kind']=='file']
    if len(entries)!=1:raise ValueError('APK inventory mismatch')
    with tempfile.TemporaryDirectory(dir=output) as d:
        apk=Path(d)/'shell.apk';dump_entry(image,entries[0],apk)
        if digest(apk)!=policy['apk_sha256']:raise ValueError('Wrong original APK')
        with zipfile.ZipFile(apk) as z:
            matches=[i for i in z.infolist() if i.filename==policy['member']]
            if len(matches)!=1 or matches[0].file_size!=policy['library_size_bytes']:
                raise ValueError('Wrong library member')
            blob=z.read(matches[0])
        library=output/'libshell.so';library.write_bytes(blob)
        if digest(library)!=policy['library_sha256']:raise ValueError('Wrong original library')
    text,_=command(['readelf','--dyn-syms','-W',str(library)])
    selected=select_symbols(text);ranges=executable_ranges(blob)
    for entry in selected:
        if not any(a<=entry['elf_address'] and entry['elf_address']+entry['size_bytes']<=b for a,b in ranges):
            raise ValueError('Export is not in file-backed executable memory')
    (output/'shell-functions.txt').write_text(''.join(f"{x['elf_address']:x}\n" for x in selected))
    (output/'shell-strings.json').write_text('[]\n')
    (output/'shell-entry-selection.json').write_text(json.dumps({'policy':policy,'selected':selected,
        'library_executed':False,'jni_signatures_validated':False,'port_ready':False},indent=2)+'\n')
    return selected

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('images','reconstruction','output'):p.add_argument('--'+name,required=True)
    a=p.parse_args();prepare(a.images,a.reconstruction,a.output)
