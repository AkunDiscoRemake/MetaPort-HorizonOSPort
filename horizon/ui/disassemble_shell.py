# SPDX-License-Identifier: GPL-3.0-only
"""Stream all objdump executable-section output for pinned libshell into a bounded gzip.

Not whole-Horizon recovery, source code, reachable-code proof, or execution.
"""
import argparse
import gzip
import hashlib
import json
from pathlib import Path
import re
import subprocess
import tempfile
from horizon.ui.prepare_shell import POLICY, executable_ranges

ROW=re.compile(rb'^\s*[0-9a-f]+:\s+[0-9a-f]{8}\s+(\S+)')
MAX_TEXT=1024*1024*1024
MAX_GZIP=256*1024*1024


def stream_listing(lines,destination,max_bytes=MAX_TEXT):
    counts={'text_bytes':0,'lines':0,'instruction_rows':0,'directive_rows':0}
    with gzip.GzipFile(filename=str(destination),mode='wb',mtime=0) as output:
        for line in lines:
            counts['text_bytes']+=len(line);counts['lines']+=1
            if counts['text_bytes']>max_bytes:raise ValueError('Disassembly text budget')
            match=ROW.match(line)
            if match:
                key='directive_rows' if match[1].startswith(b'.') else 'instruction_rows'
                counts[key]+=1
            output.write(line)
            if output.fileobj.tell()>MAX_GZIP:raise ValueError('Compressed listing budget')
    if not counts['instruction_rows']:raise ValueError('No ARM64 instruction rows; not successful disassembly')
    return counts


def run(library,output):
    library=Path(library);output=Path(output);output.mkdir(parents=True,exist_ok=True)
    blob=library.read_bytes();policy=json.loads(POLICY.read_text())
    if len(blob)!=policy['library_size_bytes'] or hashlib.sha256(blob).hexdigest()!=policy['library_sha256']:
        raise ValueError('Unpinned original library')
    executable_ranges(blob)
    target=output/'libshell-executable-sections.asm.gz'
    command=['aarch64-linux-gnu-objdump','--disassemble','--wide','--demangle',str(library)]
    version=subprocess.check_output([command[0],'--version'],text=True).splitlines()[0]
    with tempfile.TemporaryFile() as errors:
        process=subprocess.Popen(command,stdout=subprocess.PIPE,stderr=errors)
        try:
            counts=stream_listing(process.stdout,target)
            result=process.wait(timeout=30)
            errors.seek(0);diagnostic=errors.read(8192).decode(errors='replace')
            if result:raise ValueError(f'objdump exit {result}: {diagnostic}')
        except BaseException:
            process.kill();process.wait();target.unlink(missing_ok=True);raise
        finally:process.stdout.close()
    digest=hashlib.sha256()
    with target.open('rb') as data:
        for block in iter(lambda:data.read(1024*1024),b''):digest.update(block)
    report={'library_sha256':policy['library_sha256'],'tool':version,
            'command':command,'listing_sha256':digest.hexdigest(),'gzip_bytes':target.stat().st_size,
            **counts,'firmware_executed':False,'runtime_validated':False,'all_horizon_disassembled':False,
            'scope':'All sections selected by objdump --disassemble in this single original ELF; data directives and unreachable code may appear',
            'license_note':'Original Meta code disassembly is not relicensed under the project GPL',
            'stderr_prefix':diagnostic}
    (output/'shell-full-disassembly.json').write_text(json.dumps(report,indent=2)+'\n')
    return report

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--library',required=True);p.add_argument('--output',required=True)
    a=p.parse_args();run(a.library,a.output)
