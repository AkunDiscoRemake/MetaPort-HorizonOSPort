"""Bounded ramdisk inventory. No filesystem extraction, mounts, chroot or guest execution.
Supports gzip, raw newc CPIO, and LZ4 (optional pinned Python lz4 package).
"""
import hashlib
import io
from pathlib import PurePosixPath
import struct
import zlib

MAX_UNPACKED=128*1024*1024
MAX_FILES=30000


def decompress(blob):
    if blob.startswith(b'\x1f\x8b'):
        result=bytearray()
        remaining=blob
        while remaining:
            dec=zlib.decompressobj(31)
            data=dec.decompress(remaining, MAX_UNPACKED-len(result)+1)
            result.extend(data)
            if len(result)>MAX_UNPACKED or not dec.eof: raise ValueError('Gzip limit/truncation')
            remaining=dec.unused_data.lstrip(b'\0')
        return bytes(result),'gzip'
    if blob.startswith(b'\x02\x21\x4c\x18'):
        import lz4.block
        result=bytearray(); offset=4
        while offset<len(blob):
            if offset+4>len(blob): raise ValueError('Truncated legacy LZ4 size')
            size=struct.unpack_from('<I',blob,offset)[0]; offset+=4
            if not size:
                if any(blob[offset:]): raise ValueError('Trailing legacy LZ4 data')
                break
            if size>16*1024*1024 or offset+size>len(blob): raise ValueError('Invalid legacy LZ4 block')
            result.extend(lz4.block.decompress(blob[offset:offset+size],uncompressed_size=8*1024*1024))
            if len(result)>MAX_UNPACKED: raise ValueError('LZ4 limit')
            offset+=size
        return bytes(result),'lz4-legacy'
    if blob.startswith(b'\x04\x22\x4d\x18'):
        import lz4.frame
        with lz4.frame.open(io.BytesIO(blob),'rb') as stream:
            data=stream.read(MAX_UNPACKED+1)
        if len(data)>MAX_UNPACKED: raise ValueError('LZ4 frame limit')
        return data,'lz4-frame'
    if blob.startswith((b'070701',b'070702')):
        if len(blob)>MAX_UNPACKED: raise ValueError('Raw CPIO limit')
        return blob,'none'
    raise ValueError('Unsupported ramdisk compression')


def inventory(blob):
    data,compression=decompress(blob)
    offset=0; entries=[]; configs=[]; trailers=0
    while offset<len(data):
        # Multiple padded newc archives are permitted; never follow paths or symlinks.
        if data[offset]==0:
            offset+=1; continue
        if offset+110>len(data) or data[offset:offset+6] not in (b'070701',b'070702'):
            raise ValueError('Invalid newc header')
        magic=data[offset:offset+6]
        try: fields=[int(data[offset+6+i*8:offset+14+i*8],16) for i in range(13)]
        except ValueError as exc: raise ValueError('Invalid newc hex field') from exc
        inode,mode,uid,gid,nlink,mtime,size,devmajor,devminor,rdevmajor,rdevminor,namesize,checksum=fields
        if namesize<1 or namesize>4096 or offset+110+namesize>len(data): raise ValueError('Invalid CPIO name')
        rawname=data[offset+110:offset+110+namesize]
        if rawname[-1:]!=b'\0' or b'\0' in rawname[:-1]: raise ValueError('Invalid CPIO name terminator')
        name=rawname[:-1].decode('utf-8','strict')
        start=(offset+110+namesize+3)&~3
        if start+size>len(data): raise ValueError('CPIO data exceeds archive')
        content=data[start:start+size]
        if magic==b'070702' and sum(content)&0xffffffff!=checksum: raise ValueError('CPIO checksum mismatch')
        offset=(start+size+3)&~3
        if name=='TRAILER!!!':
            if size: raise ValueError('Nonempty CPIO trailer')
            trailers+=1; continue
        path=PurePosixPath(name)
        if path.is_absolute() or '..' in path.parts: raise ValueError('Unsafe CPIO path')
        normalized=str(path)
        kind={0o100000:'file',0o040000:'directory',0o120000:'symlink'}.get(mode&0o170000,'special')
        entry={'path':normalized,'kind':kind,'size_bytes':size,'mode':oct(mode),'uid':uid,'gid':gid,
               'sha256':hashlib.sha256(content).hexdigest() if kind=='file' else None}
        if kind=='symlink': entry['target']=content.decode('utf-8','replace')
        entries.append(entry)
        if len(entries)>MAX_FILES: raise ValueError('CPIO entry limit')
        if kind=='file' and size<=256*1024 and (
            path.name.startswith('fstab.') or path.suffix=='.rc' or path.name in ('prop.default','default.prop')):
            text=content.decode('utf-8','replace')
            configs.append({'path':normalized,'sha256':entry['sha256'], 'text':text})
    if trailers==0: raise ValueError('Missing CPIO trailer')
    return {'compression':compression,'unpacked_size_bytes':len(data),'archive_trailers':trailers,
            'entries':entries,'configuration':configs,'executed':False}
