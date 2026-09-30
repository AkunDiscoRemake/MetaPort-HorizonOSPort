# SPDX-License-Identifier: GPL-3.0-only
"""Static pointer evidence from original ELF words and supported readelf relocations.

ELF VAs throughout; never execute code, apply a private ABI or resolve external
symbols. RAW64 matches may be integers. Even local symbol bindings can be
interposed at runtime. Packed relocations/relative C++ vtables remain unresolved.
"""
import json
from pathlib import Path
import re
import struct
from collections import defaultdict, Counter


def load_segments(data):
    if len(data)<64 or data[:6]!=b'\x7fELF\x02\x01' or struct.unpack_from('<H',data,18)[0]!=183:
        raise ValueError('Expected AArch64 ELF64 little endian')
    phoff=struct.unpack_from('<Q',data,32)[0]
    size,count=struct.unpack_from('<HH',data,54)
    if size!=56 or not 0<count<=128 or phoff+size*count>len(data):
        raise ValueError('Program header bounds')
    segments=[]
    for i in range(count):
        kind,flags,offset,va,physical,filesz,memsz,align=struct.unpack_from('<II6Q',data,phoff+i*size)
        if kind!=1: continue
        if offset+filesz>len(data) or filesz>memsz or va+memsz>1<<64:
            raise ValueError('Load segment bounds')
        if any(va<s['va']+s['memsz'] and s['va']<va+memsz for s in segments):
            raise ValueError('Ambiguous load VA ranges')
        segments.append(dict(va=va,offset=offset,filesz=filesz,memsz=memsz,flags=flags))
    if not segments: raise ValueError('No load segments')
    return segments


def parse_relocations(text):
    resolved={}; kinds=Counter(); parsed=Counter()
    for line in text.splitlines():
        m=re.match(r'^\s*([0-9a-fA-F]+)\s+([0-9a-fA-F]+)\s+(R_AARCH64_\w+)\s+(.*?)\s*$',line)
        if not m: continue
        slot,info=int(m[1],16),int(m[2],16); kind=m[3]; kinds[kind]+=1
        target=None
        if kind=='R_AARCH64_RELATIVE' and info>>32==0 and re.fullmatch(r'[0-9a-fA-F]+',m[4]):
            target=int(m[4],16)
        elif kind=='R_AARCH64_ABS64':
            symbol=re.fullmatch(r'([0-9a-fA-F]+)\s+\S+\s+\+\s+([0-9a-fA-F]+)',m[4])
            if symbol and int(symbol[1],16)!=0: target=int(symbol[1],16)+int(symbol[2],16)
        if target is None: continue
        if slot%8 or not 0<=target<1<<64: raise ValueError('Invalid pointer relocation')
        if slot in resolved: raise ValueError('Duplicate relocation slot')
        resolved[slot]=(target,kind);parsed[kind]+=1
        if len(resolved)>1000000: raise ValueError('Relocation count limit')
    return resolved, {'observed_types':dict(kinds),'resolved_types':dict(parsed),
                      'complete_relocation_coverage':False}


class PointerIndex:
    def __init__(self,data,relocations):
        self.data=data;self.segments=load_segments(data);self.relocations=relocations
        self.reverse=defaultdict(list);count=0
        for seg in self.segments:
            if seg['flags']&1: continue
            start=(-seg['va'])%8
            for relative in range(start,max(start,seg['filesz']-7),8):
                slot=seg['va']+relative
                value,kind=self.pointer(slot)
                if value and self.segment(value):
                    self.reverse[value].append((slot,kind));count+=1
                    if count>1000000: raise ValueError('Pointer index limit')

    def segment(self,va):
        return next((s for s in self.segments if s['va']<=va<s['va']+s['memsz']),None)

    def pointer(self,va):
        seg=self.segment(va)
        if not seg or va+8>seg['va']+seg['filesz']: return (0,'UNMAPPED_OR_BSS')
        if va in self.relocations: return self.relocations[va]
        return struct.unpack_from('<Q',self.data,seg['offset']+va-seg['va'])[0],'RAW64_CANDIDATE'

    def trace(self,targets):
        results=[]
        for target in targets:
            if not any(name in target['text'] for name in ('DPEPredictorV2','getHandTrackingThreadPriorityCallback')): continue
            names=self.reverse.get(target['address'],[])
            row={'text':target['text'],'string_elf_address':target['address'],
                 'name_pointer_count':len(names),'name_pointers_truncated':len(names)>64,'paths':[]}
            for name_slot,name_kind in names[:64]:
                if name_slot<8: continue
                typeinfo=name_slot-8
                refs=self.reverse.get(typeinfo,[])
                for type_slot,type_kind in refs[:64]:
                    path={'name_slot_elf':name_slot,'name_pointer_kind':name_kind,
                          'hypothetical_typeinfo_elf':typeinfo,'type_reference_slot_elf':type_slot,
                          'type_pointer_kind':type_kind,'type_reference_count':len(refs),
                          'type_references_truncated':len(refs)>64,'executable_pointer_candidates':[]}
                    for i in range(16):
                        slot=type_slot+8+i*8;pointer,kind=self.pointer(slot);seg=self.segment(pointer)
                        if pointer%4==0 and seg and seg['flags']&1 and pointer<seg['va']+seg['filesz']:
                            path['executable_pointer_candidates'].append({'slot_elf':slot,'target_elf':pointer,'pointer_kind':kind})
                    row['paths'].append(path)
            results.append(row)
        return {'targets':results,'private_abi_validated':False,'firmware_executed':False,
                'scope':'64-bit raw/RELATIVE/local ABS64 pointer evidence; +8 RTTI hypothesis; 16 adjacent slots not an established vtable extent'}


def prepare(output):
    import hashlib
    from horizon.tracking.prepare_input import ENGINE_SHA
    from tools.scan_partitions import command
    output=Path(output);binary=output/'libtrackingengines.so';data=binary.read_bytes()
    if hashlib.sha256(data).hexdigest()!=ENGINE_SHA: raise ValueError('Wrong engine')
    text,diagnostics=command(['readelf','-rW',str(binary)],max_output=64*1024*1024)
    relocations,stats=parse_relocations(text)
    report=PointerIndex(data,relocations).trace(json.loads((output/'optimization-all-strings.json').read_text()))
    report.update(engine_sha256=ENGINE_SHA,relocations=stats,readelf_diagnostics=diagnostics)
    (output/'hand-optimization-elf-pointers.json').write_text(json.dumps(report,indent=2)+'\n')
    return report


if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('output',type=Path)
    prepare(p.parse_args().output)
