"""Derive vbmeta digest/size boot parameters; NOT a trusted bootloader verifier.

Uses the AVB header, footer and chain descriptor formats. No flag/signature/image
patching. The original guest libavb still performs its verification. A root key
anchor and hardware rollback state are NOT supplied or authenticated here.
"""
import hashlib
from pathlib import Path
import re
import stat
import struct

MAX_VBMETA=1024*1024


def read_vbmeta(path):
    path=Path(path)
    if not stat.S_ISREG(path.lstat().st_mode): raise ValueError('Expected regular AVB image')
    size=path.stat().st_size;offset=0;bound=size
    with path.open('rb') as stream:
        if stream.read(4)!=b'AVB0':
            if size<64: raise ValueError('Missing AVB header/footer')
            stream.seek(size-64);footer=stream.read(64)
            if footer[:4]!=b'AVBf': raise ValueError('Missing AVB footer')
            offset,footer_size=struct.unpack_from('>QQ',footer,20)
            if offset+footer_size>size-64: raise ValueError('AVB footer out of bounds')
            bound=offset+footer_size
        stream.seek(offset);header=stream.read(256)
        if len(header)!=256 or header[:4]!=b'AVB0': raise ValueError('Bad vbmeta header')
        auth,aux=struct.unpack_from('>QQ',header,12)
        total=256+auth+aux
        if total>MAX_VBMETA or offset+total>bound: raise ValueError('vbmeta exceeds bounds')
        if struct.unpack_from('>I',header,120)[0]&3: raise ValueError('Disabled AVB flags not accepted')
        stream.seek(offset);blob=stream.read(total)
    desc_offset,desc_size=struct.unpack_from('>QQ',header,96)
    if desc_offset+desc_size>aux: raise ValueError('Descriptor table out of bounds')
    cursor=256+auth+desc_offset;end=cursor+desc_size;chains=[]
    while cursor<end:
        if cursor+16>end: raise ValueError('Truncated AVB descriptor')
        tag,length=struct.unpack_from('>QQ',blob,cursor)
        stop=cursor+16+length
        if length%8 or stop>end: raise ValueError('Invalid descriptor size')
        if tag==4:
            if length<76: raise ValueError('Short chain descriptor')
            name_size,key_size=struct.unpack_from('>II',blob,cursor+20)
            if cursor+92+name_size+key_size>stop: raise ValueError('Chain bounds')
            name=blob[cursor+92:cursor+92+name_size].decode('ascii')
            if not re.fullmatch(r'[A-Za-z0-9_]{1,35}',name): raise ValueError('Unsafe chain name')
            chains.append(name)
        cursor=stop
    return blob,chains


def parameters(images):
    images=Path(images);seen=set();parts=[];digest=hashlib.sha256();total=0
    def visit(name):
        nonlocal total
        if name in seen or len(seen)>=16: raise ValueError('Duplicate/cyclic or oversized vbmeta chain')
        seen.add(name);blob,chains=read_vbmeta(images/(name+'.img'))
        digest.update(blob);total+=len(blob)
        parts.append({'name':name,'size_bytes':len(blob),'sha256':hashlib.sha256(blob).hexdigest()})
        for child in chains: visit(child)
    visit('vbmeta')
    return {'hash_alg':'sha256','size':total,'digest':digest.hexdigest(),'chain':parts,
            'trust_anchor_verified':False,'rollback_protection_emulated':False,
            'verification_disabled':False,'note':'Derived handoff digest only; not proof of Meta authenticity or hardware Verified Boot.'}
