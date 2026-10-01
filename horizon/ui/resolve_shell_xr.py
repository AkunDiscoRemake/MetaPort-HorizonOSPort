# SPDX-License-Identifier: GPL-3.0-only
"""Resolve original OpenXR procedure-name bytes referenced by recovered C-like calls.

No library loading, authentication, server access, or private ABI fabrication.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
from handtracking.ai.elf_pointer_evidence import load_segments
from horizon.ui.prepare_shell import POLICY

NAME=re.compile(r'xr[A-Z][A-Za-z0-9_]{1,127}\Z')
CALL=re.compile(r'\b(xr[A-Z][A-Za-z0-9_]*)\s*\(')


def call_arguments(text, start):
    """Bounded balanced parentheses; return top-level arguments and next offset."""
    depth=1;args=[];begin=start;quote=None;escaped=False
    for i in range(start,min(len(text),start+4096)):
        char=text[i]
        if quote:
            if escaped: escaped=False
            elif char=='\\': escaped=True
            elif char==quote: quote=None
            continue
        if char in ('"',"'"): quote=char
        elif char=='(': depth+=1
        elif char==')':
            depth-=1
            if depth==0:return args+[text[begin:i].strip()],i+1
        elif char==',' and depth==1:
            args.append(text[begin:i].strip());begin=i+1
            if len(args)>16:raise ValueError('Argument budget')
    raise ValueError('Unterminated or excessive call')


def string_at(data,segments,address):
    for seg in segments:
        if seg['flags']&1:continue
        if seg['va']<=address<seg['va']+seg['filesz']:
            offset=seg['offset']+address-seg['va']
            end=min(offset+256,seg['offset']+seg['filesz'])
            raw=data[offset:end];nul=raw.find(b'\0')
            if nul<0:return None
            try: value=raw[:nul].decode('ascii')
            except UnicodeDecodeError:return None
            return value if NAME.fullmatch(value) else None
    return None


def resolve(data,report):
    if report.get('image_base')!='00100000' or report.get('firmware_executed') is not False:
        raise ValueError('Unsupported evidence base/scope')
    segments=load_segments(data);rows=[]
    functions=report['functions']
    if len(functions)>96:raise ValueError('Function budget')
    for function in functions:
        if function['status']!='DECOMPILED_NOT_VALIDATED':continue
        code=function.get('c_like','')
        if len(code)>200000:raise ValueError('C-like budget')
        # Mask literals and comments together, preserving positions; text inside a
        # log message must not become a call, nor may URL slashes hide real code.
        tokens=r'"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'|/\*.*?\*/|//[^\n]*'
        code=re.sub(tokens,lambda m:' '*len(m[0]),code,flags=re.S)
        for match in CALL.finditer(code):
            row={'caller_elf':function['elf_address'],'api':match[1],
                 'evidence':'DECOMPILER_CALL_CANDIDATE_NOT_RUNTIME'}
            if match[1]=='xrGetInstanceProcAddr':
                try:args,_=call_arguments(code,match.end())
                except ValueError:args=[]
                pointer=re.fullmatch(r'&DAT_([0-9a-fA-F]{8,16})',args[1]) if len(args)==3 else None
                if pointer:
                    address=int(pointer[1],16)-0x100000
                    row['name_string_elf']=address
                    name=string_at(data,segments,address)
                    if name:row['requested_procedure']=name
                if 'requested_procedure' not in row:
                    row['name_resolution']='UNRESOLVED_NOT_ASSUMED_SUPPORTED'
            rows.append(row)
            if len(rows)>1024:raise ValueError('Call-site budget')
    return {'call_sites':rows,'runtime_executed':False,'private_abi_validated':False,
            'extension_support_verified':False,
            'scope':'Direct C-like calls and hash-pinned procedure-name strings; optionality and indirect calls unresolved'}


def run(library,evidence,output):
    policy=json.loads(POLICY.read_text());library=Path(library)
    if library.stat().st_size!=policy['library_size_bytes']:raise ValueError('Wrong library size')
    data=library.read_bytes()
    if hashlib.sha256(data).hexdigest()!=policy['library_sha256']:raise ValueError('Wrong library hash')
    evidence=Path(evidence)
    if evidence.stat().st_size>16*1024*1024:raise ValueError('Evidence budget')
    raw=evidence.read_bytes();report=json.loads(raw)
    if report['program_sha256'].lower()!=policy['library_sha256']:raise ValueError('Wrong decompilation hash')
    result=resolve(data,report)
    result.update(library_sha256=policy['library_sha256'],evidence_sha256=hashlib.sha256(raw).hexdigest())
    output=Path(output);output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps(result,indent=2)+'\n')
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('library','evidence','output'):p.add_argument('--'+name,required=True)
    a=p.parse_args();run(a.library,a.evidence,a.output)
