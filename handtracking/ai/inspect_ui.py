"""Decompile original UI DEX on a runner; publish bounded contract evidence only."""
import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import zipfile
from tools.scan_partitions import dump_entry, command, elf_report
from handtracking.ai.inspect_original import digest, BUILD
from horizon.ui.evidence import summarize_ux

APKS = ['/priv-app/VrShell/VrShell.apk', '/priv-app/MetaSystemUI/MetaSystemUI.apk']
INPUT_CALL = re.compile(r'nativeKeyEvent|nativeJoypadAxis|nativeOnInputDevice|nativeRequestUpdateGamepadInputMode|IHandTracking|IInputDataInjection')
CONTRACT = re.compile(r'\bnative\b|loadLibrary\(|ServiceManager\.|getService\(|hand.?track|controller|onKeyEvent|onGenericMotionEvent|onHand|MemoryBroker', re.I)


def summarize_sources(root):
    files = sorted(Path(root).rglob('*.java'))
    if len(files) > 100000: raise ValueError('Source count limit')
    result = {'generated_java_files': len(files), 'files_with_decompiler_errors': 0,
              'native_declarations_total': 0, 'contracts': [], 'input_call_sites': [],
              'source_is_reconstructed_not_original': True, 'runtime_validated': False}
    # Prefer the original UI namespaces, not unrelated dependencies' controller names.
    files.sort(key=lambda p: (0 if any(x in str(p) for x in ('/com/oculus/','/com/meta/')) else 1 if 'systemui' in str(p).lower() else 2, str(p)))
    for path in files:
        if path.stat().st_size > 4*1024*1024: raise ValueError('Generated source size limit')
        text = path.read_text(errors='replace')
        failed = bool(re.search(r'JADX ERROR|Method not decompiled:', text))
        result['files_with_decompiler_errors'] += int(failed)
        result['native_declarations_total'] += len(re.findall(r'\bnative\s+[\w<>\[\].?]+\s+\w+\s*\(', text))
        lines=text.splitlines()
        for index,line in enumerate(lines):
            if INPUT_CALL.search(line) and len(result['input_call_sites'])<100:
                start=max(0,index-12);end=min(len(lines),index+13)
                result['input_call_sites'].append({'path':str(path.relative_to(root)),
                    'line':index+1,'start_line':start+1,'generated_sha256':digest(path),
                    'has_decompiler_errors':failed,'context':'\n'.join(lines[start:end])})
        selected = [{'line': n, 'text': line.strip()[:1200]} for n,line in enumerate(text.splitlines(),1)
                    if CONTRACT.search(line)]
        if selected and len(result['contracts']) < 160:
            result['contracts'].append({'path': str(path.relative_to(root)), 'generated_sha256': digest(path),
                'has_decompiler_errors': failed, 'matching_lines': len(selected), 'selected_lines': selected[:60]})
    return result


def inspect(images, reconstruction, jadx, output):
    output=Path(output);output.mkdir(parents=True, exist_ok=True)
    partition='system_ext';image=Path(images)/(partition+'.img')
    expected=json.loads(Path(reconstruction).read_text())['partitions'][partition]['sha256']
    if digest(image)!=expected: raise ValueError('Partition hash mismatch')
    inventory=json.loads(Path(f'analysis/builds/{BUILD}/static-analysis.json').read_text())['partitions'][partition]['entries']
    entries={e['path']:e for e in inventory if e['kind']=='file'}
    report={'build':BUILD,'tool':'JADX 1.5.6','firmware_executed':False,'ui_ported':False,'applications':[]}
    for path in APKS:
        with tempfile.TemporaryDirectory(dir=output) as temp:
            root=Path(temp);apk=root/'original.apk';dump_entry(image,entries[path],apk)
            manifest,_=command(['aapt','dump','xmltree',str(apk),'AndroidManifest.xml'],max_output=4*1024*1024)
            native=[]
            with zipfile.ZipFile(apk) as archive:
                name='lib/arm64-v8a/libshell.so'
                if name in archive.namelist():
                    entry=archive.getinfo(name)
                    if entry.file_size>128*1024*1024: raise ValueError('Native library size limit')
                    library=root/'libshell.so';library.write_bytes(archive.read(entry))
                    native.append({'apk_member':name,**elf_report(library,deep=False)})
            env=dict(os.environ,JAVA_OPTS='-Xmx4g')
            with (root/'jadx.log').open('w') as log:
                try:
                    run=subprocess.run([str(jadx),'--threads-count','2','--decompilation-mode','restructure',
                        '--output-dir',str(root/'generated'),str(apk)],stdout=log,stderr=subprocess.STDOUT,
                        timeout=900,env=env,check=False)
                    status='COMPLETED' if run.returncode==0 else 'COMPLETED_WITH_ERRORS'
                    code=run.returncode
                except subprocess.TimeoutExpired:
                    status='TIMED_OUT_PARTIAL_OUTPUT';code=None
            item={'path':path,'sha256':digest(apk),'manifest':manifest,'decompiler_status':status,
                  'native_libraries':native,'exit_code':code,**summarize_sources(root/'generated'),
                  'ux_evidence':summarize_ux(root/'generated'),
                  'log_tail':'\n'.join((root/'jadx.log').read_text(errors='replace').splitlines()[-40:])}
            report['applications'].append(item)
            (output/'ui-decompilation.json').write_text(json.dumps(report,indent=2)+'\n')


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('images','reconstruction','jadx','output'): p.add_argument('--'+name,required=True)
    a=p.parse_args();inspect(a.images,a.reconstruction,Path(a.jadx).resolve(),a.output)
