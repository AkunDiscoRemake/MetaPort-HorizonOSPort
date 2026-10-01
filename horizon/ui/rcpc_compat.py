# SPDX-License-Identifier: GPL-3.0-only
"""Explicit one-site RCpc -> RCsc load adaptation for translated CI only.

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


def lower_verified(data,expected_sha=ORIGINAL_SHA,pc=PC):
    sha=hashlib.sha256(data).hexdigest()
    if sha!=expected_sha:raise ValueError('RCpc adaptation requires exact original libc++ hash')
    matches=[s for s in load_segments(data) if s['flags']&1 and s['va']<=pc and pc+4<=s['va']+s['filesz']]
    if len(matches)!=1 or pc%4:raise ValueError('RCpc site not unique executable word')
    segment=matches[0];offset=segment['offset']+pc-segment['va']
    if struct.unpack_from('<I',data,offset)[0]!=BEFORE:raise ValueError('Wrong original RCpc instruction')
    result=bytearray(data);struct.pack_into('<I',result,offset,AFTER)
    return bytes(result),{'library':'libc++.so','source_sha256':sha,
        'adapted_sha256':hashlib.sha256(result).hexdigest(),'pc_elf':pc,'file_offset':offset,
        'original_word':hex(BEFORE),'adapted_word':hex(AFTER),
        'operation':'ldaprb w8, [x8] -> ldarb w8, [x8]',
        'scope':'Single explicit stronger-acquire instruction adaptation for CI translation',
        'physical_device_validated':False,'complete_cpu_compatibility':False}
