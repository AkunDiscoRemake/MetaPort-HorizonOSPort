# SPDX-License-Identifier: GPL-3.0-only
"""Verified hand service/config and accelerator dependency inventory. No execution."""
import json
import hashlib
from collections import Counter
from pathlib import Path
import re
import struct
import tempfile
from horizon.tracking.inspect_original import BUILD, digest
from horizon.tracking.hvx_evidence import HvxEvidence
from tools.scan_partitions import command, dump_entry

PATHS = {
    'odm': ('/etc/trackingservice.cfg', '/etc/init/odm.trackingservice.rc',
            '/etc/init/apex.trackingservice.rc', '/lib64/libhzos_trackinghost.meta.so',
            '/lib64/libtrackingvendorutils.so'),
    'vendor': ('/lib64/libhexagon.so', '/lib64/libhexagon_shim.so',
               '/lib64/libcdsprpc.so', '/lib64/libadsprpc.so',
               '/lib/rfsa/adsp/libhexagon_skel.so',
               '/lib/rfsa/adsp/libQnnBoltnnOpPackageV69.so'),
}
PATTERN = re.compile(r'hand|tracking|wakeup|uclamp|cpuset|\bdpe\b|microgesture|schedul|affinity|thread|priority|batch|pool|predict|downsampl|quant|hexagon|fastrpc|cdsprpc', re.I)


def elf_identity(data):
    if len(data) < 52 or data[:4] != b'\x7fELF' or data[4] not in (1, 2) or data[5] not in (1, 2):
        raise ValueError('Invalid ELF identity')
    if data[4] == 2 and len(data) < 64:
        raise ValueError('Truncated ELF64')
    machine = struct.unpack_from('<H' if data[5] == 1 else '>H', data, 18)[0]
    return {'bits': 32 if data[4] == 1 else 64, 'byte_order': 'little' if data[5] == 1 else 'big',
            'flags': struct.unpack_from('<I' if data[5]==1 else '>I',data,36 if data[4]==1 else 48)[0],
            'machine': machine, 'architecture': {183: 'AArch64', 164: 'Hexagon'}.get(machine, 'OTHER')}


def executable_section_view(data):
    """Analysis-only ELF32 section view over original executable PT_LOAD bytes.

    Some DSP files have no usable section table. Preserve payload/VA/flags; append
    synthetic section metadata, never flash/load this derivative as firmware.
    """
    identity=elf_identity(data)
    if identity['bits']!=32 or identity['byte_order']!='little' or identity['machine']!=164:
        raise ValueError('Section view only supports verified little-endian Hexagon ELF32')
    phoff=struct.unpack_from('<I',data,28)[0]
    phsize,count=struct.unpack_from('<HH',data,42)
    if phsize!=32 or not 0<count<=128 or phoff+phsize*count>len(data):
        raise ValueError('Program header bounds')
    segments=[]
    for i in range(count):
        kind,offset,va,physical,size,memsize,flags,alignment=struct.unpack_from('<8I',data,phoff+i*32)
        if kind!=1: continue
        if offset+size>len(data) or size>memsize or va+memsize>1<<32:
            raise ValueError('Segment bounds')
        if flags&1 and size: segments.append((offset,va,size))
    if not segments: raise ValueError('No executable file-backed load segments')
    if sum(size for _,_,size in segments)>128*1024*1024:
        raise ValueError('Executable section view size limit')
    names=bytearray(b'\0'); descriptors=[]
    view=bytearray(data);view.extend(b'\0'*((-len(view))%4))
    for i,(offset,va,size) in enumerate(segments):
        name_offset=len(names);names.extend(f'.metaport_exec{i}\0'.encode())
        # A load segment may include the ELF header that we patch below. Decode
        # a byte-exact copy instead, keeping even those original bytes intact.
        copied_offset=len(view);view.extend(data[offset:offset+size])
        view.extend(b'\0'*((-len(view))%4))
        descriptors.append((name_offset,1,6,va,copied_offset,size,0,0,4,0))
    string_name=len(names);names.extend(b'.shstrtab\0')
    string_offset=len(view);view.extend(names);view.extend(b'\0'*((-len(view))%4))
    shoff=len(view); view.extend(bytes(40))
    for descriptor in descriptors: view.extend(struct.pack('<10I',*descriptor))
    view.extend(struct.pack('<10I',string_name,3,0,0,string_offset,len(names),0,0,1,0))
    struct.pack_into('<I',view,32,shoff)
    struct.pack_into('<HHH',view,46,40,len(segments)+2,len(segments)+1)
    return bytes(view)


def text_evidence(raw):
    if len(raw) > 1024*1024:
        return {'status': 'TEXT_SIZE_LIMIT'}
    try:
        text = raw.decode('utf-8')
    except UnicodeDecodeError:
        return {'status': 'NOT_UTF8'}
    if '\x00' in text:
        return {'status': 'BINARY_OR_NUL_TEXT'}
    lines = text.splitlines()
    matches = {i for i, line in enumerate(lines) if PATTERN.search(line)}
    context = sorted({j for i in matches for j in range(max(0,i-2),min(len(lines),i+3))})
    rows = [{'line': i+1, 'excerpt': lines[i][:1024], 'line_truncated': len(lines[i])>1024,
             'keyword_match': i in matches} for i in context]
    return {'status': 'TEXT_CANDIDATES_ONLY', 'matched_lines': len(matches),
            'context_lines': len(rows), 'lines': rows[:256], 'truncated': len(rows)>256,
            'runtime_activation_proved': False}


def disassembly_summary(text):
    """LLVM output evidence only; vector syntax does not prove hand-model activation."""
    labels=[]; vectors=[]; samples=[]; vector_count=0; instructions=0; unknown=0
    interesting=re.compile(r'conv|gemm|matmul|quant|pool|softmax|relu|hvx|vtcm|vector',re.I)
    label_count=0; operations=Counter(); hvx=HvxEvidence()
    for line in text.splitlines():
        label=re.match(r'^\s*[0-9a-fA-F]+ <(.+)>:$',line)
        if label and interesting.search(label[1]):
            label_count+=1
            if len(labels)<256: labels.append(label[1][:1024])
        if not re.match(r'^\s*[0-9a-fA-F]+:',line): continue
        hvx.feed(line)
        instructions+=1
        if len(samples)<128 and (instructions<=16 or instructions%4096==0): samples.append(line[:1024])
        if re.search(r"unknown|invalid",line,re.I): unknown+=1
        if re.search(r'\bv[0-9]+(?:\.[a-z]+)?\b',line):
            vector_count+=1
            operations.update(re.findall(r"\b(v[a-z][a-z0-9_]*)\s*\(",line))
            if len(vectors)<64: vectors.append(line[:1024])
    return {'decoded_text_sha256':hashlib.sha256(text.encode()).hexdigest(),
            'tool':'llvm-objdump-14','instruction_lines':instructions,
            'unknown_or_invalid_instruction_lines':unknown,'instruction_samples':samples,'matching_function_labels':label_count,
            'function_labels':labels,'function_labels_truncated':label_count>256,
            'vector_operation_spellings':dict(sorted(operations.items())),
            'vector_syntax_lines':vector_count,'vector_samples':vectors,
            'vector_samples_truncated':vector_count>64,
            'hvx_operand_evidence':hvx.report(),
            'hand_call_chain_validated':False,'scope':'Whole objdump text summarized; excerpts bounded, no instruction semantics validated'}



def inspect(images, reconstruction, output, disassemble=False):
    recon = json.loads(Path(reconstruction).read_text())['partitions']
    inventory = json.loads(Path(f'analysis/builds/{BUILD}/static-analysis.json').read_text())['partitions']
    result = {'firmware_executed': False, 'all_dependencies_found': False,
              'scope': 'Whitelisted service/config and RPC/backend files, not a transitive closure', 'files': []}
    with tempfile.TemporaryDirectory() as temp:
        for partition, paths in PATHS.items():
            image = Path(images)/f'{partition}.img'; expected = recon[partition]
            if not expected['sha256_match'] or image.stat().st_size != expected['size_bytes'] or digest(image) != expected['sha256']:
                raise ValueError('Unverified '+partition)
            for path in paths:
                entries = [e for e in inventory[partition]['entries'] if e['path']==path and e['kind']=='file']
                row = {'partition': partition, 'path': path}; result['files'].append(row)
                if len(entries) != 1:
                    row['status'] = 'MISSING_OR_AMBIGUOUS_INVENTORY'; continue
                local = Path(temp)/'component'; dump_entry(image, entries[0], local)
                row.update(size_bytes=local.stat().st_size, sha256=digest(local))
                if local.stat().st_size > 128*1024*1024:
                    row['status']='INSPECTION_SIZE_LIMIT'; continue
                data = local.read_bytes()
                if data.startswith(b'\x7fELF'):
                    row['elf'] = elf_identity(data)
                    dynamic, diagnostics = command(['readelf', '-dW', str(local)], max_output=1024*1024)
                    # command raises on nonzero exit; second return value is stderr.
                    row['dynamic_read_exit_code']=0
                    row['dynamic_read_diagnostics']=diagnostics
                    row['needed']=re.findall(r'\(NEEDED\).*?\[(.*?)\]',dynamic)
                    row['status']='ELF_METADATA_ONLY'
                    if disassemble and row['elf']['machine']==164:
                        assembly, diagnostics = command(['llvm-objdump-14', '--disassemble',
                            '--demangle', '--no-show-raw-insn', str(local)], max_output=64*1024*1024)
                        row['disassembly']=disassembly_summary(assembly)
                        row['disassembly']['diagnostics']=diagnostics
                        if not row['disassembly']['instruction_lines']:
                            # Empty successful objdump output is NOT successful decoding.
                            row['original_section_disassembly']=row['disassembly']
                            view=executable_section_view(data)
                            view_path=Path(temp)/'hexagon-section-view.elf';view_path.write_bytes(view)
                            assembly, diagnostics=command(['llvm-objdump-14','--disassemble',
                                '--demangle','--no-show-raw-insn',str(view_path)],max_output=64*1024*1024)
                            row['disassembly']=disassembly_summary(assembly)
                            row['disassembly']['diagnostics']=diagnostics
                            row['disassembly']['synthetic_section_view']=True
                            row['disassembly']['view_sha256']=hashlib.sha256(view).hexdigest()
                            row['disassembly']['decoded_segment_bytes_unchanged']=True
                        row['status']='DISASSEMBLED_NOT_VALIDATED' if row['disassembly']['instruction_lines'] else 'NO_DECODED_INSTRUCTIONS'
                        # LLVM 14.0.6 ELF.h: EF_HEXAGON_MACH_V69=0x69, mask=0x3ff.
                        # HVX length is a decoder hypothesis, not measured hardware state.
                        if row['elf']['flags'] & 0x3ff == 0x69:
                            target=view_path if row['disassembly'].get('synthetic_section_view') else local
                            assembly,diagnostics=command(['llvm-objdump-14','--disassemble',
                                '--no-show-raw-insn','--mcpu=hexagonv69',
                                '--mattr=+hvxv69,+hvx-length128b',str(target)],max_output=64*1024*1024)
                            row['hvx_decoder_probe']=disassembly_summary(assembly)
                            row['hvx_decoder_probe']['diagnostics']=diagnostics
                            row['hvx_decoder_probe']['hardware_vector_length_validated']=False
                            row['hvx_decoder_probe']['features']='hexagonv69,+hvxv69,+hvx-length128b'


                else:
                    row.update(text_evidence(data))
    Path(output).write_text(json.dumps(result, indent=2)+'\n')
    return result


if __name__ == '__main__':
    import argparse
    p=argparse.ArgumentParser(description=__doc__)
    for arg in ('images','reconstruction','output'): p.add_argument('--'+arg,required=True,type=Path)
    p.add_argument('--disassemble',action='store_true')
    a=p.parse_args(); inspect(a.images,a.reconstruction,a.output,a.disassemble)
