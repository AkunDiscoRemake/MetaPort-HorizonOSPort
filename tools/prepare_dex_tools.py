# SPDX-License-Identifier: GPL-3.0-only
"""Prepare pinned host-only dexlib2/baksmali tools, never Android runtime stubs.

Pins are the Maven Central published artifact SHA-1 values; also record downloaded
SHA-256 values. These tools/dependencies retain their respective upstream licenses.
"""
import hashlib
import json
from pathlib import Path
import subprocess
import urllib.request

ROOT=Path('local-analysis/dex-tools')
ARTIFACTS=(
 ('org/smali/dexlib2/2.5.2/dexlib2-2.5.2.jar','8b664182af455b0757a7f59a42020fa5608c7d0e'),
 ('org/smali/baksmali/2.5.2/baksmali-2.5.2.jar','1375ac2ff5531e14c308c0342703d9842602388f'),
 ('org/smali/util/2.5.2/util-2.5.2.jar','8aca9e1ca27ac0f6b9d42a1bbd95cde9bb5e0e12'),
 ('com/google/guava/guava/27.1-android/guava-27.1-android.jar','a80ef47421d6607e749f8b7282dd7dee61adfea7'),
 ('com/beust/jcommander/1.64/jcommander-1.64.jar','456a985ac9b12d34820e4d5de063b2c2fc43ed5a'),
 ('com/google/code/findbugs/jsr305/3.0.2/jsr305-3.0.2.jar','25ea2e8b0c338a877313bd4672d3fe056ea78f0d'),
)


WRITER_URL='https://raw.githubusercontent.com/JesusFreke/smali/v2.5.2/dexlib2/src/main/java/org/jf/dexlib2/writer/DexWriter.java'
WRITER_SHA256='7a15d75536dd7cee9d3ee65c02de9ddcdbec81456fb5fc0f0fbf4a5828e0f972'
WRITER_ANCHOR='        hiddenApiRestrictionsOffset = offsetWriter.getPosition();'


def patch_writer(data,expected_sha=WRITER_SHA256):
    if len(data)>256*1024 or hashlib.sha256(data).hexdigest()!=expected_sha:
        raise ValueError('Wrong pinned DexWriter source')
    text=data.decode('utf-8')
    if text.count(WRITER_ANCHOR)!=1:raise ValueError('Ambiguous DexWriter patch anchor')
    return text.replace(WRITER_ANCHOR,
        '        // MetaPort: preserve class_def order for hidden API metadata, not lexical order.\n'
        '        classEntries.sort(Comparator.comparingInt(entry -> entry.getValue()));\n'+WRITER_ANCHOR).encode('utf-8')


def prepare():
    ROOT.mkdir(parents=True,exist_ok=True);records=[]
    for artifact,expected in ARTIFACTS:
        url='https://repo.maven.apache.org/maven2/'+artifact
        with urllib.request.urlopen(url,timeout=45) as response:
            if not response.url.startswith('https://repo.maven.apache.org/maven2/'):
                raise ValueError('Unexpected tool download origin')
            data=response.read(16*1024*1024+1)
        if len(data)>16*1024*1024 or hashlib.sha1(data).hexdigest()!=expected:
            raise ValueError('Wrong pinned host tool artifact')
        target=ROOT/Path(artifact).name;target.write_bytes(data)
        records.append({'url':url,'published_sha1':expected,'sha256':hashlib.sha256(data).hexdigest()})
    with urllib.request.urlopen(WRITER_URL,timeout=45) as response:
        source=response.read(256*1024+1)
    patched=patch_writer(source)
    writer=ROOT/'patched-source/org/jf/dexlib2/writer/DexWriter.java'
    writer.parent.mkdir(parents=True,exist_ok=True);writer.write_bytes(patched)
    (ROOT/'classes').mkdir(exist_ok=True)
    compiled=subprocess.run(['javac','--release','11','-cp',str(ROOT/'*'),'-d',str(ROOT/'classes'),
                    'horizon/ui/java/SelectFrameworkClasses.java','horizon/ui/java/VerifyDexWriter.java',str(writer)],capture_output=True,text=True,timeout=60)
    if compiled.returncode:raise ValueError('Class selector compilation failed: '+compiled.stderr[-4000:])
    regression=[]
    for first,second,mode in ((ROOT/'*',ROOT/'classes','mismatch'),(ROOT/'classes',ROOT/'*','match')):
        checked=subprocess.run(['java','-Xmx256m','-cp',str(first)+':'+str(second),
                                'VerifyDexWriter',mode],capture_output=True,text=True,timeout=30)
        if checked.returncode:raise ValueError('DexWriter regression failed: '+checked.stderr[-4000:])
        regression.append(checked.stdout.strip())
    records.append({'url':WRITER_URL,'source_sha256':WRITER_SHA256,
                    'patched_source_sha256':hashlib.sha256(patched).hexdigest(),
                    'patch':'Order hidden API metadata by emitted class_def index',
                    'regression_results':regression,'upstream_license':'BSD-3-Clause, retained in downloaded source'})
    (ROOT/'provenance.json').write_text(json.dumps(records,indent=2)+'\n')

if __name__=='__main__':
    report={'runtime_ported':False}
    try:
        prepare();report['prepared']=True
        report['artifacts']=json.loads((ROOT/'provenance.json').read_text())
    except Exception as error:
        report.update(prepared=False,error=str(error)[:5000])
    output=Path('local-analysis/android-runtime/dex-tools-setup.json')
    output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps(report,indent=2)+'\n')
    raise SystemExit(0 if report['prepared'] else 1)
