# SPDX-License-Identifier: GPL-3.0-only
"""Explicit inventory-based RCpc -> RCsc load adaptation for translated CI only.

LDAR/LDARB retain an atomic acquire load with stronger ordering than LDAPRB.
No instruction is removed, no service/check is replaced, no success is fabricated.
This does not make the complete binary portable or validate concurrent behavior.
"""
import hashlib
import json
from pathlib import Path
import struct
from handtracking.ai.elf_pointer_evidence import load_segments

ORIGINAL_SHA='9d8e75c1c1abdecb9dcd71602aba2fa28b30c6f6918f20d6721c164fc8196d72'
PC=0x88ac4
BEFORE=0x38bfc108  # ldaprb w8, [x8]
AFTER=0x08dffd08   # ldarb w8, [x8]
def load_sites(filename='libcxx-rcpc-sites.json',expected_sha=ORIGINAL_SHA,expected_count=206):
    policy=json.loads(Path(__file__).with_name(filename).read_text())
    if policy['source_sha256']!=expected_sha or len(policy['sites'])!=expected_count:
        raise ValueError('Wrong pinned RCpc inventory')
    return tuple((r['pc_elf'],int(r['original_word'],16),int(r['adapted_word'],16)) for r in policy['sites'])


SITES=load_sites()
LIBUTILS_SHA='2d7422e92852d7c62e2528ba6100f5b484dfd33c38d156613c6aaeb89b9f9167'
LIBUTILS_SITES=load_sites('libutils-rcpc-sites.json',LIBUTILS_SHA,14)
def load_dependency_sites():
    raw=Path(__file__).with_name('dependency-rcpc-sites.json').read_bytes()
    if hashlib.sha256(raw).hexdigest()!='4531a6d2954471f0481ecfc081228f78331bdc76bc35fd2366adfe9e3a82e9b2':
        raise ValueError('Wrong pinned dependency inventory')
    return tuple((r['library'],r['source_sha256'],tuple(
        (s['pc_elf'],int(s['original_word'],16),int(s['adapted_word'],16))
        for s in r['sites'])) for r in json.loads(raw)['libraries'])


ADAPTATIONS=(('libc++.so',ORIGINAL_SHA,SITES),('libutils.so',LIBUTILS_SHA,LIBUTILS_SITES))+load_dependency_sites()


def lower_verified(data,expected_sha=ORIGINAL_SHA,sites=SITES,library="libc++.so"):
    sha=hashlib.sha256(data).hexdigest()
    if sha!=expected_sha:raise ValueError('RCpc adaptation requires exact original library hash')
    if not 1<=len(sites)<=256:raise ValueError('RCpc site budget')
    segments=load_segments(data);result=bytearray(data);changes=[];seen=set()
    for pc,before,after in sites:
        if pc in seen:raise ValueError('Duplicate RCpc site')
        seen.add(pc)
        matches=[s for s in segments if s['flags']&1 and s['va']<=pc and pc+4<=s['va']+s['filesz']]
        if len(matches)!=1 or pc%4:raise ValueError('RCpc site not unique executable word')
        # Only byte, 32-bit or 64-bit acquire loads, preserving width and non-ZR registers.
        if ((before&0xfffffc00),(after&0xfffffc00)) not in ((0x38bfc000,0x08dffc00),(0xb8bfc000,0x88dffc00),(0xf8bfc000,0xc8dffc00)) or (before&1023)!=(after&1023) or (before&31)==31:
            raise ValueError('Not a width/register-preserving acquire adaptation')
        segment=matches[0];offset=segment['offset']+pc-segment['va']
        if struct.unpack_from('<I',data,offset)[0]!=before:raise ValueError('Wrong original RCpc instruction')
        struct.pack_into('<I',result,offset,after)
        changes.append({'pc_elf':pc,'file_offset':offset,'original_word':hex(before),'adapted_word':hex(after)})
    return bytes(result),{'library':library,'source_sha256':sha,
        'adapted_sha256':hashlib.sha256(result).hexdigest(),'sites':changes,
        'operation':'LDAPRB/LDAPR -> LDARB/LDAR, preserving load width and both registers',
        'scope':'Explicit inventory-based stronger-acquire adaptations for CI; static candidates are not runtime reachability proof',
        'physical_device_validated':False,'complete_cpu_compatibility':False}
