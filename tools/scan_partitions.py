#!/usr/bin/env python3
"""Read-only ext4 inventory + bounded ELF analysis. Never runs guest programs.

Uses host debugfs/readelf/aarch64-linux-gnu-objdump. No mounts, chroot or emulation.
Other filesystem formats are reported as unsupported, never as empty/successful.
"""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import resource
import stat
import subprocess
import tempfile
import zipfile

MAX_FILES = 30000
MAX_DIRECTORIES = 5000
MAX_BINARY = 16 * 1024 * 1024
MAX_ELF_PER_PARTITION = 24
INTEREST = re.compile(r'openxr|vrapi|vrservice|tracking|compositor|surfaceflinger|timewarp|oculus|horizon|hzos|xrapp|surfaceforge|mrservice|sensoremulator|memorybroker', re.I)


def limits():
    resource.setrlimit(resource.RLIMIT_FSIZE, (128 * 1024 * 1024, 128 * 1024 * 1024))
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))


def command(args, max_output=16 * 1024 * 1024):
    # File-backed stdout prevents unbounded RAM consumption by host parsers.
    with tempfile.TemporaryFile() as out, tempfile.TemporaryFile() as err:
        result = subprocess.run(args, stdout=out, stderr=err, timeout=45,
                                preexec_fn=limits, check=False)
        out.seek(0)
        data = out.read(max_output + 1)
        err.seek(0)
        errors = err.read(4096).decode('utf-8', 'replace')
    if result.returncode or len(data) > max_output:
        raise ValueError(f'Host parser failed or exceeded limit: {args[0]} (code {result.returncode})')
    return data.decode('utf-8', 'replace'), errors


def list_ext4(image):
    pending = ['/']
    directories = 0
    visited = set()
    entries = []
    while pending:
        directory = pending.pop()
        directories += 1
        if directories > MAX_DIRECTORIES:
            raise ValueError('Directory limit exceeded')
        if not re.fullmatch(r'/[A-Za-z0-9_./+@= -]*', directory):
            raise ValueError('Unsupported directory characters')
        text, errors = command(['debugfs', '-R', f'ls -p "{directory}"', str(image)])
        if 'File not found' in errors or 'not found by ext2_lookup' in errors:
            raise ValueError('Filesystem listing failed')
        parsed = 0
        for line in text.splitlines():
            if not line.startswith('/'):
                continue
            row = line.split('/')
            if len(row) < 7:
                raise ValueError('Unrecognized debugfs listing')
            inode, mode, _, _, name, size = row[1:7]
            if name in ('.', '..') or inode == '0':
                continue
            inode, mode = int(inode), int(mode, 8)
            path = directory.rstrip('/') + '/' + name
            kind = 'directory' if stat.S_ISDIR(mode) else 'file' if stat.S_ISREG(mode) else 'symlink' if stat.S_ISLNK(mode) else 'special'
            entries.append({'path': path, 'inode': inode, 'kind': kind,
                            'size_bytes': int(size) if size else None})
            parsed += 1
            if len(entries) > MAX_FILES:
                raise ValueError('File count limit exceeded')
            if kind == 'directory' and inode not in visited:
                visited.add(inode)
                pending.append(path)
        if directory == '/' and not parsed:
            raise ValueError('No root entries; filesystem may be unsupported')
    return sorted(entries, key=lambda entry: entry['path'])


def elf_report(binary, deep=False):
    data = binary.read_bytes()
    if not data.startswith(b'\x7fELF'):
        return {'format': 'NOT_ELF'}
    headers, _ = command(['readelf', '-h', '-l', '-d', '-W', str(binary)])
    sections, _ = command(['readelf', '-S', '-W', str(binary)])
    machine = re.search(r'^\s*Machine:\s*(.+)$', headers, re.M)
    needed = re.findall(r'\(NEEDED\).*?\[(.*?)\]', headers)
    interpreter = re.search(r'Requesting program interpreter:\s*([^\]]+)', headers)
    symbols, _ = command(['readelf', '--dyn-syms', '-W', str(binary)])
    exported = []
    imported = []
    for line in symbols.splitlines():
        columns = line.split()
        if len(columns) >= 8 and columns[0].endswith(':') and columns[0][:-1].isdigit():
            (imported if columns[6] == 'UND' else exported).append(columns[7])
    result = {'format': 'ELF', 'sha256': hashlib.sha256(data).hexdigest(),
              'size_bytes': len(data), 'machine': machine.group(1) if machine else None,
              'needed': needed, 'interpreter': interpreter.group(1) if interpreter else None,
              'headers': headers, 'sections': sections,
              'exported_dynamic_symbols_count': len(exported),
              'imported_dynamic_symbols_count': len(imported),
              'exported_dynamic_symbols_sample': exported[:1024],
              'imported_dynamic_symbols_sample': imported[:1024],
              'disassembly_status': 'NOT_PERFORMED'}
    # Bounded sample, not full disassembly or recovery of program semantics.
    match = re.search(r'\]\s+\.text\s+PROGBITS\s+([0-9a-fA-F]+)\s+[0-9a-fA-F]+\s+([0-9a-fA-F]+)', sections)
    if result['machine'] == 'AArch64' and match:
        start, size = int(match.group(1), 16), int(match.group(2), 16)
        stop = start + (size if deep and size <= 256 * 1024 else min(size, 4096))
        assembly, _ = command(['aarch64-linux-gnu-objdump', '-d',
                              f'--start-address={start}', f'--stop-address={stop}', str(binary)])
        result.update(disassembly_status='COMPLETE_TEXT_SECTION' if deep and stop-start==size else 'BOUNDED_TEXT_SAMPLE',
                      disassembly_start=start, disassembly_stop=stop,
                      disassembly=assembly.replace(str(binary), '<analyzed-elf>'))
    if deep:
        result['contract_strings'] = sorted(set(
            match.group().decode('ascii') for match in re.finditer(rb'[ -~]{5,512}', data)
            if re.search(rb'memorybroker|IMemoryBroker|SharedMemory|/dev/|libvrapi|libopenxr|com\.oculus|oculus\.internal', match.group(), re.I)
        ))[:512]
        try:
            rodata, _ = command(['readelf', '-x', '.rodata', str(binary)], max_output=512*1024)
            result['rodata_hex'] = rodata
        except (ValueError, OSError, subprocess.TimeoutExpired) as exc:
            result['rodata_status'] = str(exc)
    return result


def scan(image, filesystem, include_apex=True):
    if filesystem != 'ext4-family':
        return {'status': 'UNSUPPORTED_FILESYSTEM', 'filesystem': filesystem,
                'firmware_executed': False}
    entries = list_ext4(image)
    candidates = [e for e in entries if e['kind'] == 'file' and
                  0 < (e['size_bytes'] or 0) <= MAX_BINARY and
                  INTEREST.search(e['path']) and
                  (e['path'].endswith('.so') or '/bin/' in e['path'])]
    def priority(entry):
        path = entry['path']
        core = any(token in path for token in ('libmemorybroker', 'memorybrokerservice', 'libopenxr', 'libvrapi', 'libhzos', 'libxrapp', 'libsurfaceforge', 'trackingservice', 'composer-service', 'surfaceflinger'))
        priority = 0 if 'memorybroker' in path else 1 if core else 2
        return (priority, 0 if '/lib64/' in path else 1, path)
    chosen = sorted(candidates, key=priority)[:MAX_ELF_PER_PARTITION]
    reports = []
    for entry in chosen:
        with tempfile.TemporaryDirectory() as temp:
            binary = Path(temp) / 'component.bin'
            # Inode number is numeric, never use a firmware-controlled command/path.
            _, errors = command(['debugfs', '-R', f'dump <{entry["inode"]}> {binary}', str(image)])
            if not binary.is_file() or binary.stat().st_size != entry['size_bytes']:
                reports.append({'path': entry['path'], 'status': 'DUMP_FAILED'})
                continue
            try:
                report = elf_report(binary, deep=('memorybroker' in entry['path'] or 'libhzos_tracking' in entry['path']))
                report['path'] = entry['path']
                reports.append(report)
            except (ValueError, subprocess.TimeoutExpired, OSError) as exc:
                reports.append({'path': entry['path'], 'status': 'ANALYSIS_FAILED', 'error': str(exc)})
    report = {'status': 'INVENTORIED', 'filesystem': filesystem,
            'file_count': len(entries), 'kinds': dict(Counter(e['kind'] for e in entries)),
            'entries': entries, 'candidate_elf_count': len(candidates),
            'selected_elf_count': len(chosen), 'elf_analysis': reports,
            'selection_policy': 'up to 24; prioritize XR/tracking/compositor and lib64; not exhaustive',
            'firmware_executed': False, 'images_mounted': False}
    report['configuration'] = inspect_configs(image, entries)
    report['apk_analysis'] = inspect_apks(image, entries)
    if include_apex:
        report['meta_apex'] = inspect_apex(image, entries)
    return report


def dump_entry(image, entry, destination):
    if not 0 < (entry['size_bytes'] or 0) <= 128 * 1024 * 1024:
        raise ValueError('Dump exceeds limit')
    command(['debugfs', '-R', f'dump <{entry["inode"]}> {destination}', str(image)])
    if not destination.is_file() or destination.stat().st_size != entry['size_bytes']:
        raise ValueError('Dump size mismatch')


def inspect_configs(image, entries):
    results = []
    selected = [e for e in entries if e['kind'] == 'file' and
                0 < (e['size_bytes'] or 0) <= 256 * 1024 and
                (e['path'].endswith('/memorybroker_manifest.xml') or e['path'].endswith('/build.prop') or 'active_runtime.' in e['path'] or
                 ('/etc/init/' in e['path'] and e['path'].endswith('.rc')))]
    for entry in selected[:160]:
        try:
            with tempfile.TemporaryDirectory() as temp:
                target = Path(temp) / 'config'
                dump_entry(image, entry, target)
                raw = target.read_bytes()
                text = raw.decode('utf-8', 'strict')
            # Report only build identity properties or service declaration blocks,
            # not arbitrary scripts, secrets, property triggers or device actions.
            result = {'path': entry['path'], 'sha256': hashlib.sha256(raw).hexdigest()}
            if entry['path'].endswith('/memorybroker_manifest.xml'):
                import xml.etree.ElementTree as ET
                tree = ET.fromstring(text)
                result['vintf_hal'] = [{'format': h.get('format'), 'name': h.findtext('name'),
                                       'version': h.findtext('version'), 'fqname': h.findtext('fqname')}
                                      for h in tree.findall('hal')]
            elif 'active_runtime.' in entry['path']:
                manifest = json.loads(text)
                result['openxr_runtime_manifest'] = manifest
            elif entry['path'].endswith('/build.prop'):
                prefixes = ('ro.build.', 'ro.system.build.', 'ro.product.build.',
                            'ro.vendor.build.', 'ro.odm.build.', 'ro.system_ext.build.')
                result['build_properties'] = {k: v for line in text.splitlines()
                    if '=' in line for k, v in [line.split('=', 1)] if k.startswith(prefixes)}
            else:
                services = []
                current = None
                for line in text.splitlines():
                    clean = line.strip()
                    if not clean or clean.startswith('#'):
                        continue
                    if not line[0].isspace():
                        current = None
                        if clean.startswith('service '):
                            tokens = clean.split()
                            current = {'name': tokens[1], 'command': tokens[2:], 'options': []}
                            services.append(current)
                    elif current is not None and clean.split()[0] in (
                        'class', 'user', 'group', 'capabilities', 'seclabel',
                        'interface', 'disabled', 'oneshot', 'socket', 'file'):
                        current['options'].append(clean)
                result['services'] = services
            results.append(result)
        except (ValueError, OSError, subprocess.TimeoutExpired) as exc:
            results.append({'path': entry['path'], 'status': 'CONFIG_FAILED', 'error': str(exc)})
    return results


def inspect_apex(image, entries):
    results = []
    selected = [e for e in entries if e['kind'] == 'file' and
                '/apex/com.meta.' in e['path'] and e['path'].endswith('.apex')]
    for entry in selected[:8]:
        result = {'path': entry['path']}
        try:
            with tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                container = root / 'module.apex'
                dump_entry(image, entry, container)
                result['sha256'] = hashlib.sha256(container.read_bytes()).hexdigest()
                with zipfile.ZipFile(container) as archive:
                    names = archive.namelist()
                    if len(names) != len(set(names)):
                        raise ValueError('Duplicate APEX ZIP entries')
                    info = archive.getinfo('apex_payload.img')
                    if not 0 < info.file_size <= 512 * 1024 * 1024:
                        raise ValueError('APEX image exceeds limit')
                    payload = root / 'apex.img'
                    count = 0
                    digest = hashlib.sha256()
                    with archive.open(info) as source, payload.open('xb') as target:
                        while chunk := source.read(1024 * 1024):
                            count += len(chunk)
                            if count > info.file_size:
                                raise ValueError('APEX image size overflow')
                            target.write(chunk)
                            digest.update(chunk)
                    if count != info.file_size:
                        raise ValueError('Truncated APEX payload')
                    result['payload_sha256'] = digest.hexdigest()
                    result['payload_size_bytes'] = count
                with payload.open('rb') as stream:
                    prefix = stream.read(4096)
                filesystem = ('ext4-family' if prefix[1080:1082] == b'\x53\xef' else
                              'erofs' if prefix[1024:1028] == b'\xe2\xe1\xf5\xe0' else 'UNKNOWN')
                result['inventory'] = scan(payload, filesystem, include_apex=False)
                result['status'] = 'PAYLOAD_INSPECTED'
                result['signature_verified'] = False
        except (ValueError, KeyError, OSError, subprocess.TimeoutExpired, zipfile.BadZipFile) as exc:
            result.update(status='APEX_ANALYSIS_FAILED', error=str(exc))
        results.append(result)
    return results


def inspect_apks(image, entries):
    selected = [e for e in entries if e['kind'] == 'file' and
                e['path'].rsplit('/', 1)[-1] in (
                    'VrDriver.apk', 'VrShell.apk', 'MetaSystemUI.apk',
                    'SystemActivities.apk', 'PresenceService.apk')]
    results = []
    for entry in selected[:8]:
        result = {'path': entry['path'], 'firmware_executed': False}
        try:
            with tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                apk = root / 'package.apk'
                dump_entry(image, entry, apk)
                result['sha256'] = hashlib.sha256(apk.read_bytes()).hexdigest()
                try:
                    manifest, _ = command(['aapt', 'dump', 'xmltree', str(apk), 'AndroidManifest.xml'])
                    result['android_manifest_xmltree'] = manifest
                except (ValueError, OSError, subprocess.TimeoutExpired) as exc:
                    result['manifest_status'] = 'PARSE_FAILED'
                    result['manifest_error'] = str(exc)
                with zipfile.ZipFile(apk) as archive:
                    names = archive.namelist()
                    if len(names) != len(set(names)):
                        raise ValueError('Duplicate APK entries')
                    result['dex_entries'] = [n for n in names if re.fullmatch(r'classes[0-9]*\.dex', n)]
                    native = [i for i in archive.infolist() if i.filename.startswith('lib/') and i.filename.endswith('.so')]
                    result['native_libraries'] = [{'path': i.filename, 'size_bytes': i.file_size} for i in native]
                    result['native_analysis'] = []
                    arm64 = sorted([i for i in native if i.filename.startswith('lib/arm64-v8a/')],
                        key=lambda i: (0 if any(token in i.filename.lower() for token in (
                            'openxr', 'vrapi', 'vrruntime', 'vrshell', 'tracking', 'compositor')) else 1,
                            i.filename))
                    for index, info in enumerate(arm64[:8]):
                        if not 0 < info.file_size <= 64 * 1024 * 1024:
                            result['native_analysis'].append({'path': info.filename, 'status': 'SIZE_LIMIT'})
                            continue
                        binary = root / f'lib{index}.so'
                        with archive.open(info) as source, binary.open('xb') as target:
                            size = 0
                            while chunk := source.read(1024 * 1024):
                                size += len(chunk)
                                if size > info.file_size:
                                    raise ValueError('APK library size exceeded')
                                target.write(chunk)
                        if size != info.file_size:
                            raise ValueError('APK library truncated')
                        try:
                            native_result = elf_report(binary, deep=info.filename.endswith('/libopenxr_forwardloader.so'))
                            native_result['path'] = info.filename
                            result['native_analysis'].append(native_result)
                        except (ValueError, OSError, subprocess.TimeoutExpired) as exc:
                            result['native_analysis'].append({'path': info.filename, 'status': 'ANALYSIS_FAILED', 'error': str(exc)})
                result['status'] = 'APK_STATIC_INSPECTION'
                result['signature_verified'] = False
                result['dex_decompiled'] = False
        except (ValueError, OSError, KeyError, subprocess.TimeoutExpired, zipfile.BadZipFile) as exc:
            result.update(status='APK_ANALYSIS_FAILED', error=str(exc))
        results.append(result)
    return results


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--images', required=True, type=Path)
    parser.add_argument('--reconstruction-report', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    reconstruction = json.loads(args.reconstruction_report.read_text())
    report = {'schema_version': 1, 'port_status': 'NOT PORTED YET', 'partitions': {}}
    for name, data in reconstruction['partitions'].items():
        if not re.fullmatch(r'[A-Za-z0-9_-]+', name):
            raise ValueError('Invalid partition name')
        try:
            image = args.images / (name + '.img')
            report['partitions'][name] = scan(image, data['filesystem_magic'])
            if data['filesystem_magic'] == 'UNKNOWN':
                from tools.boot_metadata import inspect_image
                report['partitions'][name]['image_metadata'] = inspect_image(image)
                report['partitions'][name]['filesystem_status'] = report['partitions'][name]['status']
                report['partitions'][name]['status'] = 'RAW_IMAGE_METADATA'
        except (ValueError, subprocess.TimeoutExpired, OSError) as exc:
            report['partitions'][name] = {'status': 'SCAN_FAILED', 'error': str(exc)}
        print(name, report['partitions'][name]['status'], flush=True)
    args.output.write_text(json.dumps(report, indent=2, ensure_ascii=True) + '\n')


if __name__ == '__main__':
    main()
