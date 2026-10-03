# SPDX-License-Identifier: GPL-3.0-only
"""Stream executable-section assembly for a hash-pinned original ARM64 ELF.

Not whole-Horizon recovery, source code, reachable-code proof, or execution.
"""
import gzip
import hashlib
from pathlib import Path
import re
import subprocess
import tempfile
from handtracking.ai.elf_pointer_evidence import load_segments

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


def disassemble_verified(library,target,expected_sha256,expected_size):
    library=Path(library);target=Path(target)
    if library.stat().st_size!=expected_size:
        raise ValueError('Unpinned original library size')
    blob=library.read_bytes()
    if hashlib.sha256(blob).hexdigest()!=expected_sha256:
        raise ValueError('Unpinned original library hash')
    segments=load_segments(blob)
    if not any(s['flags']&1 and s['filesz'] for s in segments):
        raise ValueError('No file-backed executable segment')
    target.parent.mkdir(parents=True,exist_ok=True)
    command=['aarch64-linux-gnu-objdump','--disassemble','--disassemble-zeroes','--wide','--demangle',str(library)]
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
    report={'library_sha256':expected_sha256,'tool':version,
            'command':command,'listing_sha256':digest.hexdigest(),'gzip_bytes':target.stat().st_size,
            **counts,'zero_runs_requested':True,'firmware_executed':False,'runtime_validated':False,'all_horizon_disassembled':False,
            'scope':'All sections selected by objdump --disassemble in this single original ELF; data directives and unreachable code may appear',
            'license_note':'Original Meta code disassembly is not relicensed under the project GPL',
            'stderr_prefix':diagnostic}
    return report

