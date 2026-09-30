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

MAX_FILES = 30000
MAX_DIRECTORIES = 5000
MAX_BINARY = 16 * 1024 * 1024
MAX_ELF_PER_PARTITION = 16
INTEREST = re.compile(r'openxr|vrapi|vrservice|tracking|compositor|surfaceflinger|timewarp|oculus|horizon', re.I)


def limits():
    resource.setrlimit(resource.RLIMIT_FSIZE, (16 * 1024 * 1024, 16 * 1024 * 1024))
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


def elf_report(binary):
    data = binary.read_bytes()
    if not data.startswith(b'\x7fELF'):
        return {'format': 'NOT_ELF'}
    headers, _ = command(['readelf', '-h', '-l', '-d', '-W', str(binary)])
    sections, _ = command(['readelf', '-S', '-W', str(binary)])
    machine = re.search(r'^\s*Machine:\s*(.+)$', headers, re.M)
    needed = re.findall(r'\(NEEDED\).*?\[(.*?)\]', headers)
    interpreter = re.search(r'Requesting program interpreter:\s*([^\]]+)', headers)
    result = {'format': 'ELF', 'sha256': hashlib.sha256(data).hexdigest(),
              'size_bytes': len(data), 'machine': machine.group(1) if machine else None,
              'needed': needed, 'interpreter': interpreter.group(1) if interpreter else None,
              'headers': headers, 'sections': sections,
              'disassembly_status': 'NOT_PERFORMED'}
    # Bounded sample, not full disassembly or recovery of program semantics.
    match = re.search(r'\]\s+\.text\s+PROGBITS\s+([0-9a-fA-F]+)\s+[0-9a-fA-F]+\s+([0-9a-fA-F]+)', sections)
    if result['machine'] == 'AArch64' and match:
        start, size = int(match.group(1), 16), int(match.group(2), 16)
        stop = start + min(size, 4096)
        assembly, _ = command(['aarch64-linux-gnu-objdump', '-d',
                              f'--start-address={start}', f'--stop-address={stop}', str(binary)])
        result.update(disassembly_status='BOUNDED_TEXT_SAMPLE',
                      disassembly_start=start, disassembly_stop=stop,
                      disassembly=assembly.replace(str(binary), '<analyzed-elf>'))
    return result


def scan(image, filesystem):
    if filesystem != 'ext4-family':
        return {'status': 'UNSUPPORTED_FILESYSTEM', 'filesystem': filesystem,
                'firmware_executed': False}
    entries = list_ext4(image)
    candidates = [e for e in entries if e['kind'] == 'file' and
                  0 < (e['size_bytes'] or 0) <= MAX_BINARY and
                  INTEREST.search(e['path']) and
                  (e['path'].endswith('.so') or '/bin/' in e['path'])]
    chosen = candidates[:MAX_ELF_PER_PARTITION]
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
                report = elf_report(binary)
                report['path'] = entry['path']
                reports.append(report)
            except (ValueError, subprocess.TimeoutExpired, OSError) as exc:
                reports.append({'path': entry['path'], 'status': 'ANALYSIS_FAILED', 'error': str(exc)})
    return {'status': 'INVENTORIED', 'filesystem': filesystem,
            'file_count': len(entries), 'kinds': dict(Counter(e['kind'] for e in entries)),
            'entries': entries, 'candidate_elf_count': len(candidates),
            'selected_elf_count': len(chosen), 'elf_analysis': reports,
            'selection_policy': 'lexicographic first 16 matching filenames; not an exhaustive dependency analysis',
            'firmware_executed': False, 'images_mounted': False}


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
            report['partitions'][name] = scan(args.images / (name + '.img'), data['filesystem_magic'])
        except (ValueError, subprocess.TimeoutExpired, OSError) as exc:
            report['partitions'][name] = {'status': 'SCAN_FAILED', 'error': str(exc)}
        print(name, report['partitions'][name]['status'], flush=True)
    args.output.write_text(json.dumps(report, indent=2, ensure_ascii=True) + '\n')


if __name__ == '__main__':
    main()
