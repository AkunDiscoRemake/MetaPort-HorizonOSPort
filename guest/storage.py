"""Build a disposable GPT disk with Android LP v10.0 metadata and original images.

Format reference (Apache-2.0 AOSP): android-14.0.0_r1, system/core,
fs_mgr/liblp/include/liblp/metadata_format.h. No mounting or device writes.
This constructs a new guest layout, NOT the original headset's disk geometry.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import stat
import struct
import subprocess
import uuid
import zlib

MIB=1024*1024
MAX_DISK=8*1024*MIB
LOGICAL=('system','system_ext','vendor','odm','vendor_dlkm','odm_dlkm','product')
META_MAX=65536
SLOTS=2


def align(value,unit=MIB):
    return (value+unit-1)//unit*unit


def name36(name):
    if not re.fullmatch(r'[A-Za-z0-9_]{1,35}',name): raise ValueError('Invalid LP name')
    return name.encode().ljust(36,b'\0')


def lp_metadata(sizes):
    """Single-device, readonly linear partitions, explicit _a names, no snapshots."""
    if not sizes or len(sizes)>32: raise ValueError('Invalid partition count')
    first=align(4096+2*4096+2*SLOTS*META_MAX)
    cursor=first; partitions=[]; extents=[]; layout=[]
    for i,(name,size) in enumerate(sizes.items()):
        if size<=0 or size%4096 or size>MAX_DISK: raise ValueError('Invalid logical image size')
        partitions.append(struct.pack('<36sIIII',name36(name+'_a'),1,i,1,0))
        extents.append(struct.pack('<QIQI',size//512,0,cursor//512,0))
        layout.append({'name':name,'offset':cursor,'size_bytes':size})
        cursor=align(cursor+size)
    if cursor>MAX_DISK: raise ValueError('Super exceeds resource limit')
    group=struct.pack('<36sIQ',name36('default'),0,0)
    device=struct.pack('<QIIQ36sI',first//512,MIB,0,cursor,name36('super'),0)
    tables=b''.join(partitions+extents)+group+device
    header=bytearray(128)
    struct.pack_into('<IHHI',header,0,0x414c5030,10,0,128)
    struct.pack_into('<I',header,44,len(tables));header[48:80]=hashlib.sha256(tables).digest()
    offset=0
    for index,(count,size) in enumerate(((len(sizes),52),(len(sizes),24),(1,48),(1,64))):
        struct.pack_into('<III',header,80+index*12,offset,count,size);offset+=count*size
    header[12:44]=hashlib.sha256(header).digest()
    metadata=bytes(header)+tables
    if len(metadata)>META_MAX: raise ValueError('Metadata too large')
    metadata=metadata.ljust(META_MAX,b'\0')
    geometry=bytearray(struct.pack('<II32sIII',0x616c4467,52,bytes(32),META_MAX,SLOTS,4096))
    geometry[8:40]=hashlib.sha256(geometry).digest()
    geometry=bytes(geometry).ljust(4096,b'\0')
    prefix=bytes(4096)+geometry*2+metadata*(SLOTS*2)
    return prefix,layout,cursor


def gpt(partitions):
    """Primary+backup GPT and protective MBR; all positions in bytes in report."""
    cursor=MIB; layout=[]
    for name,size in partitions.items():
        if size<=0 or size%512: raise ValueError('Unaligned GPT partition')
        layout.append({'name':name,'offset':cursor,'size_bytes':size})
        cursor=align(cursor+size)
    total=align(cursor+34*512)
    if total>MAX_DISK or len(layout)>128: raise ValueError('GPT exceeds limit')
    sectors=total//512
    entries=bytearray(128*128)
    namespace=uuid.UUID('d68fffcf-7c90-4e40-8ff0-8fca6eec47af')
    for i,item in enumerate(layout):
        encoded=item['name'].encode('utf-16-le')
        if len(encoded)>72: raise ValueError('GPT name too long')
        struct.pack_into('<16s16sQQQ72s',entries,128*i,
                         uuid.UUID('0fc63daf-8483-4772-8e79-3d69d8477de4').bytes_le,
                         uuid.uuid5(namespace,item['name']).bytes_le,item['offset']//512,
                         (item['offset']+item['size_bytes'])//512-1,0,encoded)
    def header(current,backup,table):
        data=bytearray(512)
        struct.pack_into('<8sIIIIQQQQ16sQIII',data,0,b'EFI PART',0x10000,92,0,0,
                         current,backup,34,sectors-34,namespace.bytes_le,table,128,128,zlib.crc32(entries))
        struct.pack_into('<I',data,16,zlib.crc32(data[:92]))
        return bytes(data)
    mbr=bytearray(512)
    struct.pack_into('<B3sB3sII',mbr,446,0,b'\0\x02\0',0xee,b'\xff'*3,1,min(sectors-1,0xffffffff))
    mbr[510:512]=b'\x55\xaa'
    return [(0,bytes(mbr)),(512,header(1,sectors-1,2)),(1024,bytes(entries)),
            ((sectors-33)*512,bytes(entries)),((sectors-1)*512,header(sectors-1,1,sectors-33))],layout,total


def copy_verified(stream,path,offset,expected):
    digest=hashlib.sha256();count=0;stream.seek(offset)
    with path.open('rb') as source:
        while chunk:=source.read(MIB):
            count+=len(chunk)
            if count>expected['size_bytes']: raise ValueError('Image grew while copying')
            digest.update(chunk);stream.write(chunk)
    if count!=expected['size_bytes'] or digest.hexdigest()!=expected['sha256']:
        raise ValueError('Reconstruction hash mismatch while copying '+path.name)


def build(images,reconstruction,output):
    images=Path(images); output=Path(output)
    output.mkdir(parents=True,exist_ok=True)
    if any(output.iterdir()): raise ValueError('Use an empty output directory')
    evidence=json.loads(Path(reconstruction).read_text())['partitions']
    for name in (*LOGICAL,'vbmeta','vbmeta_system'):
        path=images/(name+'.img')
        if not stat.S_ISREG(path.lstat().st_mode): raise ValueError('Only regular image files accepted')
        if not evidence[name]['sha256_match'] or path.stat().st_size!=evidence[name]['size_bytes']:
            raise ValueError('Image not verified')
    prefix,logical,super_size=lp_metadata({n:evidence[n]['size_bytes'] for n in LOGICAL})
    fresh=output/'metadata.img'
    with fresh.open('xb') as stream: stream.truncate(64*MIB)
    subprocess.run(['mkfs.ext4','-q','-F','-L','metadata',str(fresh)],check=True)
    fresh_info={'size_bytes':fresh.stat().st_size,'sha256':hashlib.sha256(fresh.read_bytes()).hexdigest()}
    physical={'super':super_size,'metadata':64*MIB,
              'vbmeta_a':align(evidence['vbmeta']['size_bytes']),
              'vbmeta_system_a':align(evidence['vbmeta_system']['size_bytes'])}
    headers,parts,total=gpt(physical)
    locations={p['name']:p['offset'] for p in parts}
    target=output/'guest-disk.raw'
    try:
        with target.open('xb') as disk:
            disk.truncate(total)
            for offset,data in headers: disk.seek(offset);disk.write(data)
            disk.seek(locations['super']);disk.write(prefix)
            for item in logical:
                name=item['name'];copy_verified(disk,images/(name+'.img'),locations['super']+item['offset'],evidence[name])
            for name in ('vbmeta','vbmeta_system'):
                copy_verified(disk,images/(name+'.img'),locations[name+'_a'],evidence[name])
            copy_verified(disk,fresh,locations['metadata'],fresh_info)
    except Exception:
        target.unlink(missing_ok=True);raise
    report={'size_bytes':total,'physical_partitions':parts,'logical_partitions':logical,
            'lp_version':'10.0','lp_metadata_sha256':hashlib.sha256(prefix).hexdigest(),
            'source_images':{n:evidence[n] for n in (*LOGICAL,'vbmeta','vbmeta_system')},
            'metadata_origin':'Fresh disposable empty ext4; not headset userdata or secrets',
            'original_partition_bytes_modified':False,'avb_disabled':False,
            'original_disk_geometry_reproduced':False,'slot':'_a','phone_modified':False}
    (output/'storage-report.json').write_text(json.dumps(report,indent=2)+'\n')
    return report


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for option in ('images','reconstruction','output'):p.add_argument('--'+option,required=True)
    a=p.parse_args();build(a.images,a.reconstruction,a.output)
