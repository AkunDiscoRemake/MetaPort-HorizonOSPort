# SPDX-License-Identifier: GPL-3.0-only
"""Verify original DEX declaration against the normal ARM64 return path, offline."""
import argparse
import hashlib
import json
from pathlib import Path
import struct
import tempfile
import zipfile
from horizon.ui.dex_contract import Dex, MAX_DEX
from horizon.ui.prepare_shell import POLICY, executable_ranges
from horizon.ui.inspect_platform import verify_partition
from handtracking.ai.inspect_original import digest, BUILD
from tools.scan_partitions import dump_entry, command

ABI_POLICY=Path(__file__).with_name('shell-abi-policy.json')


def read_va(blob,va,size):
    executable_ranges(blob) # Also validates ELF64, machine and program header table.
    off=struct.unpack_from('<Q',blob,32)[0];entry,count=struct.unpack_from('<HH',blob,54)
    matches=[]
    for i in range(count):
        typ,flags,fileoff,start,_,filesz,_,_=struct.unpack_from('<IIQQQQQQ',blob,off+i*entry)
        if typ==1 and flags&1 and start<=va and va+size<=start+filesz:
            begin=fileoff+va-start
            if begin+size>len(blob):raise ValueError('Truncated executable bytes')
            matches.append(blob[begin:begin+size])
    if len(matches)!=1:raise ValueError('Ambiguous/unmapped executable VA')
    return matches[0]


def page_address(word,pc,register):
    if word&0x9f000000!=0x90000000 or word&31!=register:raise ValueError('Expected ADRP register')
    imm=((word>>5)&0x7ffff)<<2 | ((word>>29)&3)
    if imm&(1<<20):imm-=1<<21
    return (pc&~4095)+(imm<<12)


def slot_address(page,word,base,load):
    opcode=0xf9400000 if load else 0xf9000000
    if word&0xffc00000!=opcode or word&31!=0 or (word>>5)&31!=base:
        raise ValueError('Expected 64-bit X0 load/store')
    return page+((word>>10)&4095)*8


def disassemble(blob,start,end):
    from capstone import Cs, CS_ARCH_ARM64, CS_MODE_LITTLE_ENDIAN
    if start%4 or end%4 or not start<end or end-start>16384:raise ValueError('Disassembly extent')
    raw=read_va(blob,start,end-start)
    engine=Cs(CS_ARCH_ARM64,CS_MODE_LITTLE_ENDIAN);engine.detail=True
    instructions=list(engine.disasm(raw,start))
    if sum(i.size for i in instructions)!=len(raw):raise ValueError('Undecoded instruction bytes')
    return [{'elf_va':i.address,'bytes':i.bytes.hex(),'mnemonic':i.mnemonic,'operands':i.op_str,
             'writes':[i.reg_name(r) for r in i.regs_access()[1]]} for i in instructions]


def prove_return(blob,p):
    word=lambda va:struct.unpack('<I',read_va(blob,va,4))[0]
    page=page_address(word(p['return_page_instruction']),p['return_page_instruction'],19)
    result_slot=slot_address(page,word(p['return_load_instruction']),19,True)
    page=page_address(word(p['service_setter_page_instruction']),p['service_setter_page_instruction'],8)
    stored_slot=slot_address(page,word(p['service_setter_store_instruction']),8,False)
    if result_slot!=stored_slot:raise ValueError('Return slot differs from service setter')
    phoff=struct.unpack_from('<Q',blob,32)[0];stride,count=struct.unpack_from('<HH',blob,54)
    writable=False
    for i in range(count):
        typ,flags,_,start,_,_,memsz,_=struct.unpack_from('<IIQQQQQQ',blob,phoff+i*stride)
        writable |= typ==1 and bool(flags&2) and start<=result_slot and result_slot+8<=start+memsz
    if not writable:raise ValueError('Returned global is not in writable load memory')
    epilogue=disassemble(blob,p['return_load_instruction'],p['return_instruction']+4)
    if word(p['return_instruction'])!=0xd65f03c0:raise ValueError('Expected RET X30')
    allowed={'ldr','ldur','ldp','cmp','b.ne','add','ret'}
    for ins in epilogue[1:]:
        if ins['mnemonic'] not in allowed or {'x0','w0'}&set(ins['writes']):
            raise ValueError('Unexpected epilogue or return register clobber')
    # This proves the sequential normal-return path only, not stack-check failure
    # branches, exception cleanup, successful constructor completion or ownership.
    return {'normal_return_register':'x0','return_width_bits':64,'returned_global_elf_va':result_slot,
            'service_setter_writes_same_slot':True,'normal_epilogue':epilogue,
            'scope':'Normal sequential epilogue only; constructor, exceptions and runtime not executed'}


def inspect_wrapper(blob,symbols):
    rows=[line.split() for line in symbols.splitlines() if len(line.split())>=8 and line.split()[7]=='__wrap__ZdlPv']
    report={'symbol_rows':[' '.join(r) for r in rows[:8]],'nonreturning_claim_validated':False}
    if len(rows)!=1 or rows[0][3]!='FUNC' or rows[0][6]=='UND':
        return dict(report,status='NO_UNIQUE_DEFINED_FUNCTION')
    r=rows[0];address=int(r[1],16);size=int(r[2],0)
    report.update(elf_address=address,declared_size_bytes=size,section_index=r[6])
    if address==0:
        return dict(report,status='ZERO_ADDRESS_EXPORT_NOT_CALLABLE_PROOF')
    # Zero ELF st_size is legal for assembly/aliases, but establishes no body size.
    extent=size if size else 16
    if extent>4096:return dict(report,status='BODY_EXCEEDS_ANALYSIS_LIMIT')
    try:
        instructions=disassemble(blob,address,address+extent)
    except ValueError as error:
        return dict(report,status='NO_EXECUTABLE_WINDOW',error=str(error))
    return dict(report,status='BOUNDED_INSTRUCTIONS_ONLY',instructions=instructions,
                window_bytes=extent,complete_body_claimed=False)


def inspect(images,reconstruction,output):
    output=Path(output);output.mkdir(parents=True,exist_ok=True)
    p=json.loads(ABI_POLICY.read_text());policy=json.loads(POLICY.read_text())
    recon=json.loads(Path(reconstruction).read_text())
    if recon['source_zip_sha256']!=policy['ota_sha256']:raise ValueError('Wrong OTA')
    image=Path(images)/'system_ext.img';verify_partition(image,recon['partitions']['system_ext'])
    inv=json.loads(Path(f'analysis/builds/{BUILD}/static-analysis.json').read_text())['partitions']['system_ext']['entries']
    entries=[e for e in inv if e['kind']=='file' and e['path']==policy['apk_path']]
    if len(entries)!=1:raise ValueError('APK inventory mismatch')
    report={'source_ota_sha256':policy['ota_sha256'],'apk_sha256':policy['apk_sha256'],
            'library_sha256':policy['library_sha256'],'firmware_executed':False,
            'runtime_loaded':False,'private_service_abi_validated':False,'dex_members':[],'native_declarations':[]}
    with tempfile.TemporaryDirectory(dir=output) as temp:
        root=Path(temp);apk=root/'shell.apk';dump_entry(image,entries[0],apk)
        if digest(apk)!=policy['apk_sha256']:raise ValueError('Unpinned APK')
        with zipfile.ZipFile(apk) as archive:
            members=archive.infolist();names=[i.filename for i in members]
            if len(names)!=len(set(names)):raise ValueError('Duplicate APK entries')
            dex_members=[i for i in members if i.filename.endswith('.dex') and '/' not in i.filename]
            if not 0<len(dex_members)<=64 or sum(i.file_size for i in dex_members)>512*1024*1024:
                raise ValueError('DEX corpus budget')
            for item in dex_members:
                if item.file_size>MAX_DEX:raise ValueError('DEX file budget')
                data=archive.read(item);methods=Dex(data).native_methods(p['class_descriptor'])
                sha=hashlib.sha256(data).hexdigest()
                report['dex_members'].append({'member':item.filename,'sha256':sha,'native_methods_in_target_class':len(methods)})
                report['native_declarations'].extend(dict(m,dex_member=item.filename) for m in methods)
            init=[m for m in report['native_declarations'] if m['name']=='nativeInit']
            if len(init)!=1 or init[0]['descriptor']!=p['native_init_descriptor'] or not init[0]['static']:
                raise ValueError('DEX nativeInit contract differs from expected declaration')
            libentry=archive.getinfo(policy['member'])
            if libentry.file_size!=policy['library_size_bytes']:raise ValueError('Wrong library extent')
            blob=archive.read(libentry)
            if hashlib.sha256(blob).hexdigest()!=policy['library_sha256']:raise ValueError('Wrong original library')
            report['native_init_descriptor']=init[0]['descriptor']
            report['arm64_return']=prove_return(blob,p)
            report['cleanup_windows']=[disassemble(blob,a,b) for a,b in p['cleanup_windows']]
            report['return_type_discrepancy_resolved_for_normal_path']=True
            wrapperentry=archive.getinfo(p['wrapper_member'])
            if wrapperentry.file_size!=p['wrapper_size_bytes']:raise ValueError('Wrong wrapper member size')
            wrapper=root/'wrapper.so';wrapper.write_bytes(archive.read(wrapperentry))
            if digest(wrapper)!=p['wrapper_sha256']:raise ValueError('Wrong original wrapper library')
            symbols,_=command(['readelf','--dyn-syms','-W',str(wrapper)])
            report['delete_wrapper']={'member':p['wrapper_member'],'sha256':p['wrapper_sha256'],
                **inspect_wrapper(wrapper.read_bytes(),symbols)}
            wrapped=report['delete_wrapper']
            if wrapped.get('elf_address',0):
                from horizon.ui.trace_arm64_tail import trace_tail
                relocations,_=command(['readelf','--relocs','-W',str(wrapper)])
                wrapped['tail_trace']=trace_tail(wrapper.read_bytes(),wrapped['elf_address'],relocations)

    (output/'shell-jni-abi-proof.json').write_text(json.dumps(report,indent=2)+'\n')
    return report

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('images','reconstruction','output'):p.add_argument('--'+name,required=True)
    a=p.parse_args();inspect(a.images,a.reconstruction,a.output)
