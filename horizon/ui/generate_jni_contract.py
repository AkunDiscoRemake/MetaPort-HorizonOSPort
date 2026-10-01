# SPDX-License-Identifier: GPL-3.0-only
"""Generate type-only JNI contracts from the verified original DEX report.

No exports, stub implementations, runtime loading or private native structures.
"""
import argparse
import json
from pathlib import Path
import re
from horizon.ui.prepare_shell import POLICY

REPORT=Path('analysis/builds/52168470052900520/shell-jni-abi-proof.json')
OUTPUT=Path('port/android/adapters/src/main/cpp/shell_jni_contract.hpp')
PRIMITIVES=dict(Z='jboolean',B='jbyte',C='jchar',S='jshort',I='jint',J='jlong',F='jfloat',D='jdouble')


def descriptor_types(text):
    def read(i,allow_void=False):
        if i>=len(text):raise ValueError('Truncated descriptor')
        c=text[i]
        if c in PRIMITIVES:return PRIMITIVES[c],i+1
        if c=='V' and allow_void:return 'void',i+1
        if c=='L':
            end=text.find(';',i)
            if end<0 or not re.fullmatch(r'[A-Za-z0-9_$/]+',text[i+1:end]):
                raise ValueError('Unsupported object descriptor')
            name=text[i+1:end]
            return {'java/lang/String':'jstring','java/lang/Class':'jclass','java/lang/Throwable':'jthrowable'}.get(name,'jobject'),end+1
        if c=='[':
            start=i
            while i<len(text) and text[i]=='[':i+=1
            if i-start>255:raise ValueError('Array dimension limit')
            typ,end=read(i)
            return (typ+'Array' if i==start+1 and text[i] in PRIMITIVES else 'jobjectArray'),end
        raise ValueError('Unsupported descriptor type')
    if len(text)>4096 or not text.startswith('('):raise ValueError('Method descriptor expected')
    i=1;args=[]
    while i<len(text) and text[i]!=')':
        typ,i=read(i);args.append(typ)
    if i>=len(text):raise ValueError('Missing return descriptor')
    ret,i=read(i+1,True)
    if i!=len(text):raise ValueError('Trailing descriptor content')
    return ret,args


def generate(report):
    policy=json.loads(POLICY.read_text())
    if report['apk_sha256']!=policy['apk_sha256'] or report['library_sha256']!=policy['library_sha256']:
        raise ValueError('Unpinned original evidence')
    rows=report['native_declarations']
    if not 0<len(rows)<=256:raise ValueError('Method budget')
    out=['// SPDX-License-Identifier: GPL-3.0-only',
         '// Generated from original DEX declarations. Type contracts ONLY; not implementations.',
         '// Regenerate: python3 -m horizon.ui.generate_jni_contract',
         '#pragma once','#include <jni.h>','namespace metaport::shell::contract {']
    names=set()
    for row in sorted(rows,key=lambda r:r['name']):
        name=row['name']
        if name in names or not re.fullmatch(r'native[A-Za-z0-9_]+',name):
            raise ValueError('Overloaded/unsupported method name')
        names.add(name)
        ret,args=descriptor_types(row['descriptor'])
        params=['JNIEnv*','jclass' if row['static'] else 'jobject']+args
        out.extend(['// '+row['descriptor'],f'using {name} = {ret} (JNICALL *)('+', '.join(params)+');'])
    out.append('} // namespace metaport::shell::contract')
    return '\n'.join(out)+'\n'

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--check',action='store_true')
    args=parser.parse_args();text=generate(json.loads(REPORT.read_text()))
    if args.check:
        if OUTPUT.read_text()!=text:raise SystemExit('Generated JNI contract is stale')
    else:OUTPUT.write_text(text)
