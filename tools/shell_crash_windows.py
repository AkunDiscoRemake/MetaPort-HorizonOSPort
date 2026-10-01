# SPDX-License-Identifier: GPL-3.0-only
"""Bounded static instruction evidence for packaged ARM64 crash frames.

File bytes are not a capture of relocated process memory or proof of crash cause.
"""
import hashlib
from pathlib import Path
import re
import subprocess
import time
from handtracking.ai.elf_pointer_evidence import load_segments
from tools.scan_partitions import command

FRAME=re.compile(r'#\d+\s+pc\s+([0-9a-f]{8,16})\s+\S*/lib/arm64/([A-Za-z0-9_+.@=\-]+\.so)(?:\s|$)')


def instruction_window(data,pc,after=48):
    if not 4<=after<=1024 or after%4:raise ValueError('Instruction window budget')
    if pc%4:raise ValueError('Unaligned ARM64 PC')
    segments=load_segments(data)
    segment=next((s for s in segments if s['flags']&1 and s['va']<=pc<s['va']+s['filesz']),None)
    if segment is None:raise ValueError('PC outside file-backed executable segment')
    start=max(segment['va'],pc-16);end=min(segment['va']+segment['filesz'],pc+after)
    offset=segment['offset']+start-segment['va']
    return {'pc_elf':pc,'start_elf':start,'end_elf':end,'bytes_hex':data[offset:offset+end-start].hex()}


def collect(crash_text,libraries,bundle):
    known={n['soname']:n for n in bundle['nodes'] if 'sha256' in n}
    rows=[];seen=set();cache={};total=0
    for match in FRAME.finditer(crash_text[:65536]):
        pc=int(match[1],16);name=match[2];key=(name,pc)
        if key in seen or name not in known or '..' in name:continue
        if len(seen)>=16:break
        seen.add(key);path=Path(libraries)/name
        if name not in cache:
            size=path.stat().st_size;total+=size
            if not 0<size<=96*1024*1024 or total>256*1024*1024:raise ValueError('Crash evidence byte budget')
            data=path.read_bytes()
            if hashlib.sha256(data).hexdigest()!=known[name]['sha256']:raise ValueError('Crash library hash mismatch')
            cache[name]=data
        row={'library':name,'sha256':known[name]['sha256'],**instruction_window(cache[name],pc,after=512)}
        text,_=command(['aarch64-linux-gnu-objdump','-d','-C',
                        '--start-address='+hex(row['start_elf']),
                        '--stop-address='+hex(row['end_elf']),str(path)],max_output=65536)
        row['disassembly']=text;rows.append(row)
    # Prioritize real crash libraries, then inventory other verified small
    # dependencies so the next experiment need not discover every load singly.
    # This only collects evidence: it never selects or applies new patches.
    inventories=[];scanned=0;scan_bytes=0;candidate_count=0;started=time.monotonic()
    if len(known)>128:raise ValueError('Dependency census node budget')
    names=sorted(cache)+sorted(set(known)-set(cache))
    for name in names:
        inventory={'library':name,'sha256':known[name]['sha256'],
                   'reachable_code_proven':False,'observed_in_crash':name in cache}
        try:
            if not re.fullmatch(r'[A-Za-z0-9_][A-Za-z0-9_+.@=\-]{0,180}\.so',name) or '..' in name:
                raise ValueError('Invalid census library name')
            path=Path(libraries)/name
            if path.is_symlink():raise ValueError('Symlink census input')
            size=path.stat().st_size
            if not 0<size<=2*1024*1024 or scanned>=64 or scan_bytes+size>32*1024*1024 or time.monotonic()-started>=120 or candidate_count>=8192:
                inventory.update(inventory_complete=False,status='SKIPPED_CENSUS_BUDGET')
            else:
                scanned+=1;scan_bytes+=size
                data=cache.get(name)
                if data is None:data=path.read_bytes()
                if hashlib.sha256(data).hexdigest()!=known[name]['sha256']:
                    raise ValueError('Census library hash mismatch')
                load_segments(data)
                text,_=command(['aarch64-linux-gnu-objdump','-d',str(path)],max_output=16*1024*1024)
                candidates=rcpc_candidates(text)
                if candidate_count+len(candidates)>8192:raise ValueError('Aggregate candidate budget')
                candidate_count+=len(candidates)
                inventory.update(candidates=candidates,inventory_complete=True)
        except (ValueError,OSError,subprocess.TimeoutExpired) as error:
            # Optional failures must not erase verified crash windows.
            inventory.update(error=str(error),inventory_complete=False)
        inventories.append(inventory)
    return {'frames':rows,'rcpc_inventories':inventories,'runtime_memory_verified':False,'crash_cause_proven':False,
            'scope':'Original packaged ELF instructions at reported guest PCs; not a hardware compatibility verdict'}


def rcpc_candidates(text):
    """Decoder-labelled candidates, not proof of executed instructions or safe patches."""
    if len(text)>16*1024*1024:raise ValueError('Disassembly budget')
    pattern=re.compile(r'^\s*([0-9a-f]+):\s+([0-9a-f]{8})\s+(ldapr[bhsw]?|ldapur[bhsw]?)\s+([^\n]+)$',re.MULTILINE)
    rows=[]
    for m in pattern.finditer(text):
        if len(rows)>=4096:raise ValueError('RCpc inventory budget')
        rows.append({'pc_elf':int(m[1],16),'word':'0x'+m[2],
                     'mnemonic':m[3],'operands':m[4].strip()})
    return rows
