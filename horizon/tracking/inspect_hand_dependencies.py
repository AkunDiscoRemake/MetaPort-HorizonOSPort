# SPDX-License-Identifier: GPL-3.0-only
"""Verified hand service/config and accelerator dependency inventory. No execution."""
import hashlib
import json
from pathlib import Path
import re
import struct
import tempfile
from horizon.tracking.inspect_original import BUILD, digest
from tools.scan_partitions import command, dump_entry

PATHS = {
    'odm': ('/etc/trackingservice.cfg', '/etc/init/odm.trackingservice.rc',
            '/etc/init/apex.trackingservice.rc', '/lib64/libhzos_trackinghost.meta.so',
            '/lib64/libtrackingvendorutils.so'),
    'vendor': ('/lib64/libhexagon.so', '/lib64/libhexagon_shim.so',
               '/lib64/libcdsprpc.so', '/lib64/libadsprpc.so',
               '/lib/rfsa/adsp/libhexagon_skel.so',
               '/lib/rfsa/adsp/libQnnBoltnnOpPackageV69.so'),
}
PATTERN = re.compile(r'hand|\bdpe\b|microgesture|schedul|affinity|thread|priority|batch|pool|predict|downsampl|quant|hexagon|fastrpc|cdsprpc', re.I)


def elf_identity(data):
    if len(data) < 52 or data[:4] != b'\x7fELF' or data[4] not in (1, 2) or data[5] not in (1, 2):
        raise ValueError('Invalid ELF identity')
    if data[4] == 2 and len(data) < 64:
        raise ValueError('Truncated ELF64')
    machine = struct.unpack_from('<H' if data[5] == 1 else '>H', data, 18)[0]
    return {'bits': 32 if data[4] == 1 else 64, 'byte_order': 'little' if data[5] == 1 else 'big',
            'machine': machine, 'architecture': {183: 'AArch64', 164: 'Hexagon'}.get(machine, 'OTHER')}


def text_evidence(raw):
    if len(raw) > 1024*1024:
        return {'status': 'TEXT_SIZE_LIMIT'}
    try:
        text = raw.decode('utf-8')
    except UnicodeDecodeError:
        return {'status': 'NOT_UTF8'}
    if '\x00' in text:
        return {'status': 'BINARY_OR_NUL_TEXT'}
    rows = [{'line': i, 'excerpt': line[:1024], 'line_truncated': len(line)>1024}
            for i, line in enumerate(text.splitlines(), 1) if PATTERN.search(line)]
    return {'status': 'TEXT_CANDIDATES_ONLY', 'matched_lines': len(rows),
            'lines': rows[:256], 'truncated': len(rows)>256, 'runtime_activation_proved': False}


def inspect(images, reconstruction, output):
    recon = json.loads(Path(reconstruction).read_text())['partitions']
    inventory = json.loads(Path(f'analysis/builds/{BUILD}/static-analysis.json').read_text())['partitions']
    result = {'firmware_executed': False, 'all_dependencies_found': False,
              'scope': 'Whitelisted service/config and RPC/backend files, not a transitive closure', 'files': []}
    with tempfile.TemporaryDirectory() as temp:
        for partition, paths in PATHS.items():
            image = Path(images)/f'{partition}.img'; expected = recon[partition]
            if not expected['sha256_match'] or image.stat().st_size != expected['size_bytes'] or digest(image) != expected['sha256']:
                raise ValueError('Unverified '+partition)
            for path in paths:
                entries = [e for e in inventory[partition]['entries'] if e['path']==path and e['kind']=='file']
                row = {'partition': partition, 'path': path}; result['files'].append(row)
                if len(entries) != 1:
                    row['status'] = 'MISSING_OR_AMBIGUOUS_INVENTORY'; continue
                local = Path(temp)/'component'; dump_entry(image, entries[0], local)
                row.update(size_bytes=local.stat().st_size, sha256=digest(local))
                if local.stat().st_size > 128*1024*1024:
                    row['status']='INSPECTION_SIZE_LIMIT'; continue
                data = local.read_bytes()
                if data.startswith(b'\x7fELF'):
                    row['elf'] = elf_identity(data)
                    dynamic, code = command(['readelf', '-dW', str(local)], max_output=1024*1024)
                    row['dynamic_read_exit_code']=code
                    row['needed']=re.findall(r'\(NEEDED\).*?\[(.*?)\]',dynamic)
                    row['status']='ELF_METADATA_ONLY'
                else:
                    row.update(text_evidence(data))
    Path(output).write_text(json.dumps(result, indent=2)+'\n')
    return result


if __name__ == '__main__':
    import argparse
    p=argparse.ArgumentParser(description=__doc__)
    for arg in ('images','reconstruction','output'): p.add_argument('--'+arg,required=True,type=Path)
    a=p.parse_args(); inspect(a.images,a.reconstruction,a.output)
