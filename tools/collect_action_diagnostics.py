# SPDX-License-Identifier: GPL-3.0-only
"""Collect bounded failure diagnostics on Actions when sandbox blob downloads fail.

Uses the configured gh connection. Never requests or writes credentials.
"""
import argparse
import json
from pathlib import Path
import re
import subprocess


def api(endpoint):
    return json.loads(subprocess.check_output(['gh','api',endpoint],text=True,timeout=60))


def collect(repo,run):
    base=f'repos/{repo}'
    metadata=api(f'{base}/actions/runs/{run}')
    jobs=api(f'{base}/actions/runs/{run}/jobs?per_page=100')['jobs']
    out={'run_id':run,'source_commit':metadata['head_sha'],'status':metadata['status'],
         'conclusion':metadata['conclusion'],'jobs':[],'scope':'CI diagnostics, not runtime validation'}
    for job in jobs:
        item={'name':job['name'],'conclusion':job['conclusion'],
              'failed_steps':[s['name'] for s in job['steps'] if s.get('conclusion')=='failure']}
        if item['failed_steps']:
            logs=subprocess.run(['gh','api',f"{base}/actions/jobs/{job['id']}/logs"],capture_output=True,timeout=90)
            item['log_download_exit']=logs.returncode
            if logs.returncode==0:
                lines=logs.stdout.decode(errors='replace').splitlines()
                matches=[l for l in lines if re.search(r'error|fatal|panic|failed|timeout|not enough|no space|kvm',l,re.I)]
                # Never persist signed download links or authorization headers.
                matches=[l for l in matches if not re.search(r'authorization|[?&]sig=|github_token',l,re.I)]
                item['diagnostic_lines']=[l[:1200] for l in (matches[:35]+matches[-15:])]
            else:item['diagnostic_lines_unavailable']=True
        out['jobs'].append(item)
    return out

def captured_files(root):
    files=[]
    for path in sorted(Path(root).rglob('*')):
        if not path.is_file(): continue
        junit = path.name.startswith('TEST-') and path.suffix == '.xml'
        if not junit and path.name not in ('emulator-host.txt','boot-tail.txt','emulator-output.txt'): continue
        with path.open(errors='replace') as stream: text=stream.read(16000)
        lines=[line for line in text.splitlines() if not re.search(r'authorization|[?&]sig=|github_token',line,re.I)]
        files.append({'path':str(path.relative_to(root)), 'text':'\n'.join(lines),
                      'prefix_limit_characters':16000})
        if len(files)>=8: break
    return files


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--repo',required=True);p.add_argument('--run',type=int,required=True);p.add_argument('--output',required=True)
    p.add_argument('--artifact-root',type=Path)
    a=p.parse_args();r=collect(a.repo,a.run)
    if a.artifact_root:r['captured_files']=captured_files(a.artifact_root)
    path=Path(a.output);path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(r,indent=2)+'\n')
