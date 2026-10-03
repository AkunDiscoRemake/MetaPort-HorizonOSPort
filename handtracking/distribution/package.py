# SPDX-License-Identifier: GPL-3.0-only
"""Create auditable source/recovered bundles. Never execute original models/binaries."""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import stat
import subprocess
import zipfile

ROOT = Path(__file__).resolve().parents[2]
BUILD = '52168470052900520'
MANIFEST = 'PACKAGE-MANIFEST.json'
MAX_FILE = 128 * 1024 * 1024
MAX_TOTAL = 512 * 1024 * 1024
SOURCE_SUFFIXES = {'.py', '.cpp', '.hpp', '.h', '.java', '.md', '.json', '.txt', '.fbs', '.cmake'}


def safe_name(name):
    p = PurePosixPath(name)
    if not name or '\\' in name or ':' in name or p.is_absolute() or '..' in p.parts or str(p) != name:
        raise ValueError('Unsafe package path')
    return name


def stream_hash(stream):
    h=hashlib.sha256();size=0
    while chunk:=stream.read(1024*1024):
        size+=len(chunk)
        if size>MAX_FILE:raise ValueError('File limit')
        h.update(chunk)
    return h.hexdigest(),size


def file_info(path):
    if path.is_symlink() or not path.is_file():raise ValueError('Regular files only')
    with path.open('rb') as f:return stream_hash(f)


def read_catalog():
    return json.loads((ROOT/'handtracking/distribution/originals.json').read_text())


def expected_originals():
    expected={}
    for r in read_catalog()['resources']:
        name=safe_name('originals/'+r['partition']+'/'+r['path'].lstrip('/'))
        if name in expected:raise ValueError('Duplicate resource')
        expected[name]={'sha256':r['sha256'],'size_bytes':r['size_bytes'],'kind':r['kind']}
    policy=json.loads((ROOT/'handtracking/ai/model-evidence-policy.json').read_text())
    for path,r in policy['models'].items():
        name='originals/decoded/'+Path(path).stem+'.pte'
        if name in expected:raise ValueError('Duplicate decoded model')
        expected[name]={'sha256':r['decoded_sha256'],'kind':'decoded_original_model'}
    return expected


def extract_originals(images, reconstruction, destination):
    from tools.scan_partitions import dump_entry
    from handtracking.ai.inspect_original import digest
    from handtracking.ai.ptez import inspect_container
    images=Path(images);destination=Path(destination)
    provenance=json.loads(Path(reconstruction).read_text())
    if provenance['source_zip_sha256']!=read_catalog()['ota_sha256']:
        raise ValueError('Wrong OTA provenance')
    recon=provenance['partitions']
    inventory=json.loads((ROOT/f'analysis/builds/{BUILD}/static-analysis.json').read_text())['partitions']
    resources=read_catalog()['resources']
    for partition in sorted({r['partition'] for r in resources}):
        image=images/f'{partition}.img';r=recon[partition]
        if not r['sha256_match'] or image.stat().st_size!=r['size_bytes'] or digest(image)!=r['sha256']:
            raise ValueError('Partition verification failed')
    policy=json.loads((ROOT/'handtracking/ai/model-evidence-policy.json').read_text())['models']
    for r in resources:
        entries=[e for e in inventory[r['partition']]['entries'] if e['kind']=='file' and e['path']==r['path']]
        if len(entries)!=1:raise ValueError('Resource inventory mismatch')
        target=destination/safe_name('originals/'+r['partition']+'/'+r['path'].lstrip('/'))
        target.parent.mkdir(parents=True,exist_ok=True)
        dump_entry(images/f"{r['partition']}.img",entries[0],target)
        sha,size=file_info(target)
        if (sha,size)!=(r['sha256'],r['size_bytes']):raise ValueError('Original resource mismatch: '+r['path'])
        if r['path'].endswith('.ptez'):
            result,raw=inspect_container(target.read_bytes())
            if raw is None or result['decoded_sha256']!=policy[r['path']]['decoded_sha256']:
                raise ValueError('Decoded model mismatch')
            decoded=destination/'originals/decoded'/ (Path(r['path']).stem+'.pte')
            decoded.parent.mkdir(parents=True,exist_ok=True);decoded.write_bytes(raw)


def source_files():
    files={'README.md':ROOT/'handtracking/README.md', 'LICENSE':ROOT/'LICENSE',
           'horizon/input/original-contract.json':ROOT/'horizon/input/original-contract.json',
           'port/android/adapters/src/main/cpp/shell_jni_contract.hpp':ROOT/'port/android/adapters/src/main/cpp/shell_jni_contract.hpp',
           'NOTICE.md':ROOT/'NOTICE.md', 'THIRD-PARTY-NOTICE.md':ROOT/'handtracking/distribution/THIRD-PARTY-NOTICE.md'}
    for directory in ('handtracking','tools','horizon/ui'):
        for p in (ROOT/directory).rglob('*'):
            if p.is_file() and not p.is_symlink() and '__pycache__' not in p.parts and p.suffix in SOURCE_SUFFIXES:
                files[p.relative_to(ROOT).as_posix()]=p
    # Reports remain in their original relative paths so the AI tools/tests work.
    for p in (ROOT/f'analysis/builds/{BUILD}').iterdir():
        if p.suffix in ('.md','.json') and (p.name.lower().startswith(('hand','input-','model','ptez','reference','compressed-hand','attributes-','shell-')) or p.name in ('static-analysis.json','reconstruction.json','ui-decompilation.json','shell-hzos-native.json','shell-hzos-spaces-native.json')):
            files[p.relative_to(ROOT).as_posix()]=p
    return files


def build(output, recovered=None):
    files=source_files();originals=expected_originals() if recovered is not None else {}
    for name,expected in originals.items():
        p=Path(recovered)/name;sha,size=file_info(p)
        if sha!=expected['sha256'] or ('size_bytes' in expected and size!=expected['size_bytes']):
            raise ValueError('Missing/mismatched original: '+name)
        files[name]=p
    records=[];total=0
    for name,p in sorted(files.items()):
        safe_name(name);sha,size=file_info(p);total+=size
        if total>MAX_TOTAL:raise ValueError('Package size limit')
        records.append({'path':name,'sha256':sha,'size_bytes':size,
                        'kind':originals[name]['kind'] if name in originals else 'source_or_evidence'})
    if (ROOT/'.git').exists():
        commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
        dirty=bool(subprocess.check_output(['git','status','--porcelain'],cwd=ROOT,text=True))
    else:
        previous=json.loads((ROOT/MANIFEST).read_text()) if (ROOT/MANIFEST).exists() else {}
        commit=previous.get('source_commit','unknown');dirty=None
    manifest={'format':1,'component':'MetaPort HandTracking','source_commit':commit,'working_tree_dirty':dirty,
              'firmware_build':BUILD,'mode':'recovered' if recovered is not None else 'sources',
              'original_model_file_count':sum(r['kind']=='original_model' for r in records),
              'decoded_model_file_count':sum(r['kind']=='decoded_original_model' for r in records),
              'all_quest3_ai_recovered':False,'inference_ported':False,'phone_validated':False,
              'files':records}
    output=Path(output);output.parent.mkdir(parents=True,exist_ok=True)
    temp=output.with_suffix(output.suffix+'.partial')
    try:
        with zipfile.ZipFile(temp,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
            for r in records:
                info=zipfile.ZipInfo(r['path'],date_time=(2026,9,30,0,0,0));info.compress_type=zipfile.ZIP_DEFLATED
                info.external_attr=(stat.S_IFREG|0o644)<<16
                with files[r['path']].open('rb') as src,z.open(info,'w',force_zip64=True) as dest:
                    while chunk:=src.read(1024*1024):dest.write(chunk)
            info=zipfile.ZipInfo(MANIFEST,date_time=(2026,9,30,0,0,0));info.compress_type=zipfile.ZIP_DEFLATED
            info.external_attr=(stat.S_IFREG|0o644)<<16
            z.writestr(info,json.dumps(manifest,indent=2)+'\n')
        verify(temp)
        temp.replace(output)
    finally:
        temp.unlink(missing_ok=True)
    from handtracking.ai.inspect_original import digest
    sha=digest(output)
    output.with_suffix(output.suffix+'.sha256').write_text(f'{sha}  {output.name}\n')
    return manifest


def verify(path):
    with zipfile.ZipFile(path) as z:
        infos=z.infolist();names=[i.filename for i in infos]
        if len(names)>4096 or len(names)!=len(set(names)):raise ValueError('Duplicate/excessive entries')
        for i in infos:
            safe_name(i.filename)
            if i.file_size>MAX_FILE or stat.S_ISLNK(i.external_attr>>16):raise ValueError('Unsafe entry')
        if sum(i.file_size for i in infos)>MAX_TOTAL:raise ValueError('Archive limit')
        if z.getinfo(MANIFEST).file_size>2*1024*1024:raise ValueError('Manifest limit')
        m=json.loads(z.read(MANIFEST));rows=m['files']
        listed=[r['path'] for r in rows]
        if len(listed)!=len(set(listed)) or set(names)!=set(listed)|{MANIFEST}:raise ValueError('Unlisted/duplicate files')
        if m['mode'] not in ('sources','recovered') or m['inference_ported'] is not False or m['all_quest3_ai_recovered'] is not False:
            raise ValueError('Unsupported/completeness claim')
        for r in rows:
            with z.open(r['path']) as f:sha,size=stream_hash(f)
            if (sha,size)!=(r['sha256'],r['size_bytes']):raise ValueError('Corrupt entry: '+r['path'])
        original_rows={r['path']:r for r in rows if r['path'].startswith('originals/')}
        expected=expected_originals() if m['mode']=='recovered' else {}
        if set(original_rows)!=set(expected):raise ValueError('Original corpus mismatch')
        for name,e in expected.items():
            if original_rows[name]['sha256']!=e['sha256'] or original_rows[name]['kind']!=e['kind']:
                raise ValueError('Original fingerprint mismatch')
        for field,kind in [('original_model_file_count','original_model'),('decoded_model_file_count','decoded_original_model')]:
            if m[field]!=sum(r['kind']==kind for r in rows):raise ValueError('Model count mismatch')
        if m['phone_validated'] is not False:raise ValueError('Phone validation not established')
        return m


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output',type=Path);p.add_argument('--recovered',type=Path)
    p.add_argument('--images',type=Path);p.add_argument('--reconstruction',type=Path)
    p.add_argument('--verify',type=Path);a=p.parse_args()
    if a.verify:print(json.dumps({k:v for k,v in verify(a.verify).items() if k!='files'},indent=2))
    else:
        if not a.output:p.error('--output is required')
        if a.images:
            if not a.recovered or not a.reconstruction:p.error('Extraction requires --recovered and --reconstruction')
            extract_originals(a.images,a.reconstruction,a.recovered)
        build(a.output,a.recovered)
