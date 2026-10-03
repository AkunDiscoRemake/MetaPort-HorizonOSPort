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

APKS = ['/priv-app/VrShell/VrShell.apk', '/priv-app/MetaSystemUI/MetaSystemUI.apk',
        '/priv-app/SystemUX/SystemUX.apk', '/priv-app/SettingsPanelApp/SettingsPanelApp.apk',
        '/priv-app/LibraryPanelApp/LibraryPanelApp.apk']
UI_FRAMEWORK_JARS = ['/framework/hzos-framework.jar', '/framework/com.oculus.os.platform.jar']
CLOUD_APKS = ['/app/Store/Store.apk', '/priv-app/IdentityManagement/IdentityManagement.apk',
              '/priv-app/DeviceAuthServer/DeviceAuthServer.apk', '/priv-app/OCMS/OCMS.apk',
              '/app/SocialPlatform/SocialPlatform.apk']
INPUT_CALL = re.compile(r'nativeKeyEvent|nativeJoypadAxis|nativeOnInputDevice|nativeRequestUpdateGamepadInputMode|IHandTracking|IInputDataInjection')
CONTRACT = re.compile(r'\bnative\b|loadLibrary\(|ServiceManager\.|getService\(|hand.?track|controller|onKeyEvent|onGenericMotionEvent|onHand|MemoryBroker', re.I)


BOOTSTRAP_PATHS=tuple('sources/com/oculus/vrshell/'+name+'.java' for name in
    ('ShellApplication','HomeActivity','MainActivity','ShellActivity','EmuShellExtension','ShellService','ShellSpatialWindowManagerService')) + (
    'sources/X/C0NY.java','sources/X/C04c.java','sources/X/C0NW.java',
    'sources/X/C0NX.java','sources/X/AbstractC03500Nf.java',
    'sources/X/C00A.java','sources/X/AnonymousClass056.java',
    'sources/com/oculus/vrshell/privateipc/updater/ShellNativeUpdaterHolder.java')


def summarize_bootstrap(root):
    """Keep complete bounded startup classes, not only truncated matching lines."""
    rows=[]
    for relative in BOOTSTRAP_PATHS:
        path=Path(root)/relative
        row={'path':relative,'runtime_validated':False,'compile_ready':False}
        if not path.is_file() or path.is_symlink():
            row['status']='NOT_GENERATED_OR_NOT_REGULAR_FILE'
        elif path.stat().st_size>512*1024:
            row.update(status='OVERSIZED_NOT_EMBEDDED',size_bytes=path.stat().st_size,generated_sha256=digest(path))
        else:
            text=path.read_text(errors='replace')
            failed=bool(re.search(r'JADX ERROR|Method not decompiled:',text))
            row.update(status='RECONSTRUCTED_WITH_ERRORS' if failed else 'RECONSTRUCTED_NOT_COMPILE_VALIDATED',
                       generated_sha256=digest(path),source=text,has_decompiler_errors=failed)
        rows.append(row)
    return {'classes':rows,'scope':'Selected reconstructed original startup code, not a substitute UI or a completed port'}


def summarize_sources(root):
    files = sorted(Path(root).rglob('*.java'))
    if len(files) > 100000: raise ValueError('Source count limit')
    result = {'generated_java_files': len(files), 'files_with_decompiler_errors': 0,
              'native_declarations_total': 0, 'contracts': [], 'input_call_sites': [],
              'source_is_reconstructed_not_original': True, 'runtime_validated': False,
              'skipped_oversized_sources': [], 'source_coverage_complete': True, 'bootstrap':summarize_bootstrap(root)}
    # Prefer the original UI namespaces, not unrelated dependencies' controller names.
    files.sort(key=lambda p: (0 if any(x in str(p) for x in ('/com/oculus/','/com/meta/')) else 1 if 'systemui' in str(p).lower() else 2, str(p)))
    for path in files:
        if path.stat().st_size > 4*1024*1024:
            result['skipped_oversized_sources'].append({'path':str(path.relative_to(root)),
                'size_bytes':path.stat().st_size, 'sha256':digest(path)})
            result['source_coverage_complete'] = False
            continue
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


def archive_ui_tree(zf, prefix, generated_dir, manifest_text=None):
    root = Path(generated_dir)
    if manifest_text:
        zf.writestr(f'{prefix}/aapt-manifest-xmltree.txt', manifest_text)
    java_count = 0
    res_count = 0
    for path in sorted(root.rglob('*')):
        if not path.is_file() or path.is_symlink():
            continue
        rel = path.relative_to(root).as_posix()
        # Exclude raw native ELF .so binaries under resources/lib/ so the archive
        # contains strictly the complete decompiled UI (Java sources, XML resources,
        # layouts, drawables, manifests, and UI assets).
        if rel.startswith('resources/lib/') and rel.endswith('.so'):
            continue
        zf.write(path, f'{prefix}/{rel}')
        if rel.startswith('sources/') and rel.endswith('.java'):
            java_count += 1
        else:
            res_count += 1
    return {'java_files_archived': java_count, 'resource_files_archived': res_count}


def inspect(images, reconstruction, jadx, output, scope="ui", zip_output=None):
    output=Path(output);output.mkdir(parents=True, exist_ok=True)
    partition='system_ext';image=Path(images)/(partition+'.img')
    expected=json.loads(Path(reconstruction).read_text())['partitions'][partition]['sha256']
    if digest(image)!=expected: raise ValueError('Partition hash mismatch')
    inventory=json.loads(Path(f'analysis/builds/{BUILD}/static-analysis.json').read_text())['partitions'][partition]['entries']
    entries={e['path']:e for e in inventory if e['kind']=='file'}
    report={'build':BUILD,'tool':'JADX 1.5.6','firmware_executed':False,'ui_ported':False,'applications':[]}
    if scope not in ("ui", "cloud"): raise ValueError("Unknown analysis scope")
    report["scope"] = scope
    zf = None
    zip_manifest = {'build': BUILD, 'tool': 'JADX 1.5.6', 'modules': []}
    if zip_output is not None:
        zip_path = Path(zip_output)
        zip_path.parent.mkdir(parents=True, exist_ok=True)
        zf = zipfile.ZipFile(zip_path, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=6)
    try:
        for path in (APKS if scope == "ui" else CLOUD_APKS):
            try:
                with tempfile.TemporaryDirectory(dir=output) as temp:
                    root=Path(temp);apk=root/'original.apk';dump_entry(image,entries[path],apk)
                    manifest,_=command(['aapt','dump','xmltree',str(apk),'AndroidManifest.xml'],max_output=4*1024*1024)
                    native=[]
                    with zipfile.ZipFile(apk) as archive:
                        members = [n for n in archive.namelist() if n.startswith('lib/arm64-v8a/') and n.endswith('.so')]
                        if len(members) > 64 or sum(archive.getinfo(n).file_size for n in members) > 512*1024*1024:
                            raise ValueError('APK native library budget exceeded')
                        for index,name in enumerate(members):
                            entry=archive.getinfo(name)
                            if entry.file_size>128*1024*1024: raise ValueError('Native library size limit')
                            library=root/f'library-{index}.so';library.write_bytes(archive.read(entry))
                            try:
                                native.append({'apk_member':name,**elf_report(library,deep=False)})
                            except (ValueError, OSError, subprocess.TimeoutExpired) as error:
                                native.append({'apk_member':name, 'status':'ANALYSIS_FAILED',
                                               'sha256':digest(library), 'error':str(error)[:1000]})
                    env=dict(os.environ,JAVA_OPTS='-Xmx8g' if zf is not None else '-Xmx4g')
                    threads='4' if zf is not None else '2'
                    with (root/'jadx.log').open('w') as log:
                        try:
                            run=subprocess.run([str(jadx),'--threads-count',threads,'--decompilation-mode','restructure',
                                '--output-dir',str(root/'generated'),str(apk)],stdout=log,stderr=subprocess.STDOUT,
                                timeout=900,env=env,check=False)
                            status='COMPLETED' if run.returncode==0 else 'COMPLETED_WITH_ERRORS'
                            code=run.returncode
                        except subprocess.TimeoutExpired:
                            status='TIMED_OUT_PARTIAL_OUTPUT';code=None
                    apk_sha = digest(apk)
                    item={'path':path,'sha256':apk_sha,'manifest':manifest,'decompiler_status':status,
                          'native_libraries':native,'exit_code':code,**summarize_sources(root/'generated'),
                          'ux_evidence':summarize_ux(root/'generated'),
                          'log_tail':'\n'.join((root/'jadx.log').read_text(errors='replace').splitlines()[-40:])}
                    if zf is not None and (root/'generated').exists():
                        module_name = Path(path).stem
                        counts = archive_ui_tree(zf, module_name, root/'generated', manifest)
                        zip_manifest['modules'].append({
                            'module': module_name,
                            'source_path': path,
                            'source_sha256': apk_sha,
                            'decompiler_status': status,
                            **counts,
                        })
            except (ValueError, OSError, KeyError, subprocess.TimeoutExpired) as error:
                item = {'path':path, 'decompiler_status':'ANALYSIS_FAILED',
                        'error_type':type(error).__name__, 'error':str(error)[:2000],
                        'runtime_validated':False, 'source_is_reconstructed_not_original':True}
            report['applications'].append(item)
            (output/('ui-decompilation.json' if scope == 'ui' else 'ui-cloud-decompilation.json')).write_text(json.dumps(report,indent=2)+'\n')

        if zf is not None and scope == "ui":
            env = dict(os.environ, JAVA_OPTS='-Xmx8g')
            for jar_path in UI_FRAMEWORK_JARS:
                if jar_path not in entries:
                    continue
                with tempfile.TemporaryDirectory(dir=output) as temp:
                    root = Path(temp)
                    jar = root / 'framework.jar'
                    dump_entry(image, entries[jar_path], jar)
                    jar_sha = digest(jar)
                    with (root / 'jadx.log').open('w') as log:
                        run = subprocess.run([
                            str(jadx), '--threads-count', '4', '--decompilation-mode', 'restructure',
                            '--output-dir', str(root / 'generated'), str(jar)
                        ], stdout=log, stderr=subprocess.STDOUT, timeout=600, env=env, check=False)
                        status = 'COMPLETED' if run.returncode == 0 else 'COMPLETED_WITH_ERRORS'
                    module_name = Path(jar_path).stem
                    counts = archive_ui_tree(zf, module_name, root / 'generated')
                    zip_manifest['modules'].append({
                        'module': module_name,
                        'source_path': jar_path,
                        'source_sha256': jar_sha,
                        'decompiler_status': status,
                        **counts,
                    })
            zf.writestr('ui-decompilation.json', (output / 'ui-decompilation.json').read_text())
            zf.writestr('UI-DECOMPILATION-MANIFEST.json', json.dumps(zip_manifest, indent=2) + '\n')
            readme_lines = [
                '# Meta Horizon OS v2.7 — Complete UI Decompilation Archive',
                '',
                '- **Credits:** Meta Horizon OS v2.7 — Meta Platforms, Inc.',
                f'- **Source Firmware Build:** `{BUILD}` (`q3_52168470052900520.zip`)',
                '- **Decompiler:** JADX 1.5.6 (`--decompilation-mode restructure`)',
                '',
                '## Included Decompiled UI Modules (`sources/**` + `resources/**`)',
                '',
            ]
            for mod in zip_manifest['modules']:
                readme_lines.append(
                    f"- **`{mod['module']}/`** (`{mod['source_path']}`, SHA-256 `{mod['source_sha256']}`): "
                    f"`{mod['java_files_archived']}` `.java` files + `{mod['resource_files_archived']}` UI resource/layout/manifest/asset files"
                )
            zf.writestr('README-UI-DECOMPILATION.md', '\n'.join(readme_lines) + '\n')
    finally:
        if zf is not None:
            zf.close()

    if any(a['decompiler_status']=='ANALYSIS_FAILED' for a in report['applications']):
        raise ValueError('One or more UI applications failed; see per-application evidence')


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('images','reconstruction','jadx','output'): p.add_argument('--'+name,required=True)
    p.add_argument('--scope', choices=('ui','cloud'), default='ui')
    p.add_argument('--zip-output', default=None)
    a=p.parse_args();inspect(a.images,a.reconstruction,Path(a.jadx).resolve(),a.output,a.scope,a.zip_output)
