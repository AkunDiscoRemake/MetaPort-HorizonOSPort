# SPDX-License-Identifier: GPL-3.0-only
"""Bounded ARM64 B / conventional ELF PLT tail tracing. Never executes code."""
import struct
from horizon.ui.verify_shell_abi import read_va, page_address


def trace_tail(blob, start, relocations, limit=8):
    if not 1 <= limit <= 32:
        raise ValueError('Tail trace budget')
    result={'steps':[], 'runtime_binding_verified':False, 'callee_returns_verified':False}
    seen=set(); address=start
    for _ in range(limit):
        if address in seen:
            return dict(result,status='CYCLE')
        seen.add(address)
        try:
            word=struct.unpack('<I',read_va(blob,address,4))[0]
        except ValueError:
            return dict(result,status='UNMAPPED_TARGET',target=address)
        if word & 0xfc000000 == 0x14000000: # B, not BL
            imm=word & 0x3ffffff
            if imm & 0x2000000:imm-=0x4000000
            target=address+imm*4
            result['steps'].append(dict(elf_va=address,kind='B',target=target))
            address=target
            continue
        # Conventional AArch64 PLT: ADRP X16; LDR X17; ADD X16; BR X17.
        # BTI, authenticated or alternative stubs are deliberately unsupported.
        if word & 0x9f00001f == 0x90000010:
            try:
                _,load,add,branch=struct.unpack('<4I',read_va(blob,address,16))
            except ValueError:
                return dict(result,status='TRUNCATED_PLT')
            if (load & 0xffc003ff == 0xf9400211 and
                add & 0xffc003ff == 0x91000210 and branch == 0xd61f0220):
                offset=((load>>10)&4095)*8
                if ((add>>10)&4095)!=offset:
                    return dict(result,status='PLT_OFFSETS_DIFFER')
                slot=page_address(word,address,16)+offset
                rows=[]
                for line in relocations.splitlines():
                    cols=line.split()
                    if len(cols)<5:continue
                    try: va=int(cols[0],16)
                    except ValueError:continue
                    if va==slot:rows.append(cols)
                result['steps'].append(dict(elf_va=address,kind='PLT',got_slot=slot))
                if len(rows)==1 and rows[0][2]=='R_AARCH64_JUMP_SLOT':
                    return dict(result,status='IMPORTED_SYMBOL',symbol=rows[0][4],
                                relocation_row=' '.join(rows[0]))
                return dict(result,status='NO_UNIQUE_JUMP_SLOT')
        return dict(result,status='UNSUPPORTED_BODY',elf_va=address,first_word=hex(word))
    return dict(result,status='BUDGET_EXHAUSTED')
