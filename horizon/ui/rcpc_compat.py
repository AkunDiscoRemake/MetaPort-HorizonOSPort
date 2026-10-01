# SPDX-License-Identifier: GPL-3.0-only
"""Explicit observed-site RCpc -> RCsc load adaptation for translated CI only.

LDARB retains an atomic byte acquire load with stronger ordering than LDAPRB.
No instruction is removed, no service/check is replaced, no success is fabricated.
This does not make the complete binary portable or validate concurrent behavior.
"""
import hashlib
import struct
from handtracking.ai.elf_pointer_evidence import load_segments

ORIGINAL_SHA='9d8e75c1c1abdecb9dcd71602aba2fa28b30c6f6918f20d6721c164fc8196d72'
PC=0x88ac4
BEFORE=0x38bfc108  # ldaprb w8, [x8]
AFTER=0x08dffd08   # ldarb w8, [x8]
SITES=((PC,BEFORE,AFTER),
       (0x48cb0,0x38bfc008,0x08dffc08))  # __cxa_guard_acquire: w8, [x0]


def lower_verified(data,expected_sha=ORIGINAL_SHA,sites=SITES):
    sha=hashlib.sha256(data).hexdigest()
    if sha!=expected_sha:raise ValueError('RCpc adaptation requires exact original libc++ hash')
    segments=load_segments(data);result=bytearray(data);changes=[];seen=set()
    for pc,before,after in sites:
        if pc in seen:raise ValueError('Duplicate RCpc site')
        seen.add(pc)
        matches=[s for s in segments if s['flags']&1 and s['va']<=pc and pc+4<=s['va']+s['filesz']]
        if len(matches)!=1 or pc%4:raise ValueError('RCpc site not unique executable word')
        # Only byte acquire loads with unchanged non-ZR registers are eligible.
        if (before&0xfffffc00)!=0x38bfc000 or (after&0xfffffc00)!=0x08dffc00 or (before&1023)!=(after&1023) or (before&31)==31:
            raise ValueError('Not a register-preserving LDAPRB to LDARB adaptation')
        segment=matches[0];offset=segment['offset']+pc-segment['va']
        if struct.unpack_from('<I',data,offset)[0]!=before:raise ValueError('Wrong original RCpc instruction')
        struct.pack_into('<I',result,offset,after)
        changes.append({'pc_elf':pc,'file_offset':offset,'original_word':hex(before),'adapted_word':hex(after)})
    return bytes(result),{'library':'libc++.so','source_sha256':sha,
        'adapted_sha256':hashlib.sha256(result).hexdigest(),'sites':changes,
        'operation':'LDAPRB -> LDARB, preserving the byte load and both registers',
        'scope':'Explicit observed-site stronger-acquire instruction adaptations for CI translation',
        'physical_device_validated':False,'complete_cpu_compatibility':False}
