"""Offline hand-tracking/UI inspection; never imports or executes firmware models.

Only verified images, bounded host parsers, ZIP metadata and pickle opcodes.
Pickle GLOBAL/REDUCE instructions are reported, NEVER evaluated.
"""
import argparse
import hashlib
import io
import json
from pathlib import Path
import pickletools
import re
import tempfile
import zipfile
from tools.scan_partitions import command, dump_entry, elf_report

BUILD = '52168470052900520'
INTEREST = re.compile(r'hand|skeleton|joint|gesture|camera|calibrat|memorybroker|tracking', re.I)
ELFS = {'odm': ['/bin/trackingservice', '/lib64/libtrackingengines.so'],
        'system_ext': ['/lib64/libtrackingserviceclients.so', '/lib64/libtrackingproxy_jni.so']}
CONFIGS = {'odm': ['/etc/trackingservice.cfg', '/etc/vintf/manifest/hal_tracking_manifest.xml',
                   '/etc/init/odm.trackingservice.rc', '/etc/init/apex.trackingservice.rc'],
           'system_ext': ['/etc/permissions/com.oculus.vrshell.xml',
                          '/etc/default-permissions/com.oculus.vrshell.xml']}


def digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        while data := stream.read(1024 * 1024): h.update(data)
    return h.hexdigest()


def model_metadata(path):
    result = {'executed': False, 'format': 'UNKNOWN', 'magic_hex': path.read_bytes()[:16].hex()}
    if not zipfile.is_zipfile(path):
        return result
    with zipfile.ZipFile(path) as archive:
        entries = archive.infolist()
        if len(entries) > 10000: raise ValueError('Model ZIP entry limit')
        result.update(format='ZIP_CONTAINER', entries=[{'name': i.filename, 'size': i.file_size} for i in entries])
        streams = []
        for entry in entries:
            if not entry.filename.endswith(('bytecode.pkl', 'data.pkl')): continue
            if entry.file_size > 2 * 1024 * 1024:
                streams.append({'name': entry.filename, 'status': 'OVERSIZED_NOT_PARSED'})
                continue
            strings = set()
            try:
                for count, (op, arg, _) in enumerate(pickletools.genops(archive.read(entry))):
                    if count >= 200000: raise ValueError('Opcode limit')
                    if isinstance(arg, str) and 0 < len(arg) < 512:
                        strings.add(arg)
                streams.append({'name': entry.filename, 'status': 'OPCODES_ONLY', 'strings': sorted(strings)[:1500]})
            except (ValueError, UnicodeError) as error:
                streams.append({'name': entry.filename, 'status': 'PARSE_FAILED', 'error': str(error)[:200]})
        result['pickle_metadata'] = streams
    return result


def function_candidates(symbols, limit=24):
    candidates = []
    for line in symbols.splitlines():
        fields = line.split()
        if len(fields) < 8 or fields[3] != 'FUNC' or fields[6] == 'UND': continue
        if not re.search(r'hand|skeleton|gesture', fields[7], re.I): continue
        try: address, size = int(fields[1], 16), int(fields[2], 0)
        except ValueError: continue
        if not address or not 0 < size <= 32768: continue
        candidates.append({'address': address, 'size': size, 'symbol': fields[7]})
    # Prefer pose/update/processing contracts over constructors and logging helpers.
    candidates.sort(key=lambda x: (not bool(re.search('pose|joint|update|process|predict', x['symbol'], re.I)), x['address']))
    unique = {x['address']: x for x in reversed(candidates)}
    return sorted(unique.values(), key=lambda x: (not bool(re.search('pose|joint|update|process|predict', x['symbol'], re.I)), x['address']))[:limit]


def inspect(images, reconstruction, output):
    images, output = Path(images), Path(output)
    output.mkdir(parents=True, exist_ok=True)
    inventory = json.loads(Path(f'analysis/builds/{BUILD}/static-analysis.json').read_text())['partitions']
    verified = json.loads(Path(reconstruction).read_text())['partitions']
    report = {'build': BUILD, 'firmware_executed': False, 'hand_tracking_ported': False,
              'original_ui_ported': False, 'elf': [], 'models': [], 'configuration': [], 'ui': []}
    for partition in ('odm', 'system_ext'):
        image = images / (partition + '.img')
        if digest(image) != verified[partition]['sha256']: raise ValueError('Image hash mismatch')
        entries = {e['path']: e for e in inventory[partition]['entries'] if e['kind'] == 'file'}
        paths = ELFS[partition] + CONFIGS[partition]
        paths += [p for p in entries if p.startswith('/etc/handtracking/')]
        if partition == 'system_ext': paths += ['/priv-app/VrShell/VrShell.apk']
        for path in paths:
            entry = entries[path]
            with tempfile.TemporaryDirectory() as temp:
                binary = Path(temp) / 'component'
                dump_entry(image, entry, binary)
                base = {'partition': partition, 'path': path, 'sha256': digest(binary), 'size': binary.stat().st_size}
                if path in ELFS[partition]:
                    # Existing helper explicitly labels partial versus full .text coverage.
                    item = elf_report(binary, deep=False)
                    symbols, _ = command(['readelf', '--dyn-syms', '-W', str(binary)], max_output=64*1024*1024)
                    selected = function_candidates(symbols)
                    item['hand_related_symbols'] = [l.strip() for l in symbols.splitlines() if INTEREST.search(l)][:2000]
                    item['selected_functions'] = selected
                    item['target_disassembly'] = []
                    for func in selected:
                        asm, _ = command(['aarch64-linux-gnu-objdump', '-d', '--demangle',
                            f'--start-address={func["address"]}', f'--stop-address={func["address"]+func["size"]}', str(binary)], max_output=4*1024*1024)
                        item['target_disassembly'].append({**func, 'assembly': asm.replace(str(binary), '<original-elf>')})
                    item['dependency_strings'] = sorted(set(m.group().decode('ascii') for m in
                        re.finditer(rb'[ -~]{5,350}', binary.read_bytes()) if INTEREST.search(m.group().decode('ascii'))))[:1500]
                    report['elf'].append({**base, **item})
                    if path == '/lib64/libtrackingengines.so':
                        # Runner-local input for pinned Ghidra; never uploaded as firmware.
                        (output/'libtrackingengines.so').write_bytes(binary.read_bytes())
                        (output/'functions.json').write_text(json.dumps(selected))
                        (output/'functions.txt').write_text('\n'.join(f'{f["address"]:x}' for f in selected)+'\n')
                elif path in CONFIGS[partition]:
                    report['configuration'].append({**base, 'text': binary.read_text()})
                elif path.endswith('.apk'):
                    manifest, _ = command(['aapt', 'dump', 'xmltree', str(binary), 'AndroidManifest.xml'], max_output=4*1024*1024)
                    with zipfile.ZipFile(binary) as archive:
                        members = [{'name': e.filename, 'size': e.file_size} for e in archive.infolist()
                                   if e.filename.endswith(('.dex', '.so'))]
                    report['ui'].append({**base, 'manifest': manifest, 'code_members': members, 'executed': False})
                else:
                    report['models'].append({**base, **model_metadata(binary)})
    (output/'hand-ui-report.json').write_text(json.dumps(report, indent=2)+'\n')


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--images', required=True); p.add_argument('--reconstruction', required=True)
    p.add_argument('--output', required=True)
    a = p.parse_args(); inspect(a.images, a.reconstruction, a.output)
