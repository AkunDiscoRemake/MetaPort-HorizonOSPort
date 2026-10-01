# SPDX-License-Identifier: GPL-3.0-only
"""Bounded static instruction evidence for packaged ARM64 crash frames.

File bytes are not a capture of relocated process memory or proof of crash cause.
"""
import hashlib
from pathlib import Path
import re
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
                        '--stop-address='+hex(row['end_elf']),str(path)],max_output=16384)
        row['disassembly']=text;rows.append(row)
    inventories=[]
    if 'libc++.so' in cache:
        # Only this bounded library, and only metadata. Never bulk-rewrite matches.
        text,_=command(['aarch64-linux-gnu-objdump','-d',str(Path(libraries)/'libc++.so')],max_output=16*1024*1024)
        inventories.append({'library':'libc++.so','sha256':known['libc++.so']['sha256'],
                            'candidates':rcpc_candidates(text),'reachable_code_proven':False})
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
