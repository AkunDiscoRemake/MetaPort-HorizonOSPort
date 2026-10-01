# SPDX-License-Identifier: GPL-3.0-only
"""Read native declarations directly from standard DEX. No class loading/execution.

Only descriptors/names used here are decoded as ASCII; unrelated strings are not
materialized. This is a bounded contract reader, not a general DEX verifier.
"""
import hashlib
import struct
import zlib

MAX_DEX = 128 * 1024 * 1024

class Dex:
    def __init__(self, data):
        self.data=data
        if not 112<=len(data)<=MAX_DEX or data[:8] not in tuple(b'dex\n'+v+b'\0' for v in (b'035',b'037',b'038',b'039',b'040')):
            raise ValueError('Unsupported DEX format/size')
        if self.u32(32)!=len(data) or self.u32(36)!=112 or self.u32(40)!=0x12345678:
            raise ValueError('Invalid DEX header')
        if self.u32(8)!=(zlib.adler32(data[12:])&0xffffffff) or data[12:32]!=hashlib.sha1(data[32:]).digest():
            raise ValueError('DEX checksum/signature mismatch')
        self.tables={}
        for name,at,width in [('strings',56,4),('types',64,4),('protos',72,12),('fields',80,8),('methods',88,8),('classes',96,32)]:
            count,offset=self.u32(at),self.u32(at+4)
            if count>1000000 or (count and (offset<112 or offset%4)):
                raise ValueError('DEX table budget/alignment')
            self.bounds(offset,count*width)
            self.tables[name]=(count,offset,width)
    def bounds(self, offset, size):
        if offset<0 or size<0 or offset+size>len(self.data):raise ValueError('DEX extent out of bounds')
    def u16(self, offset):
        self.bounds(offset,2);return struct.unpack_from('<H',self.data,offset)[0]
    def u32(self, offset):
        self.bounds(offset,4);return struct.unpack_from('<I',self.data,offset)[0]
    def entry(self,name,index):
        count,offset,width=self.tables[name]
        if not 0<=index<count:raise ValueError('DEX table index')
        return offset+index*width
    def uleb(self, offset):
        value=0
        for n in range(5):
            self.bounds(offset,1);b=self.data[offset];offset+=1
            if n==4 and b&0xf0:raise ValueError('ULEB overflow')
            value|=(b&127)<<(7*n)
            if not b&128:return value,offset
        raise ValueError('ULEB overflow')
    def string(self,index):
        offset=self.u32(self.entry('strings',index));length,offset=self.uleb(offset)
        if length>4096:raise ValueError('Descriptor/name length limit')
        end=self.data.find(b'\0',offset,min(len(self.data),offset+4097))
        if end<0:raise ValueError('Unterminated DEX string')
        raw=self.data[offset:end]
        # ASCII target names/descriptors have one UTF16 code unit per byte.
        if len(raw)!=length or any(b>=128 or b==0 for b in raw):
            raise ValueError('Non-ASCII contract string unsupported')
        return raw.decode('ascii')
    def matches_string(self,index,text):
        offset=self.u32(self.entry('strings',index));length,offset=self.uleb(offset)
        raw=text.encode('ascii')
        if length!=len(raw):return False
        self.bounds(offset,len(raw)+1)
        return self.data[offset:offset+len(raw)+1]==raw+b'\0'
    def type(self,index):return self.string(self.u32(self.entry('types',index)))
    def descriptor(self,index):
        at=self.entry('protos',index);result=self.type(self.u32(at+4));params=self.u32(at+8)
        args=[]
        if params:
            if params%4:raise ValueError('Unaligned type list')
            count=self.u32(params)
            if count>128:raise ValueError('Parameter count limit')
            self.bounds(params+4,count*2)
            args=[self.type(self.u16(params+4+i*2)) for i in range(count)]
        return '('+''.join(args)+')'+result
    def native_methods(self, class_name):
        found=[]
        for i in range(self.tables['classes'][0]):
            at=self.entry('classes',i);class_index=self.u32(at)
            if not self.matches_string(self.u32(self.entry('types',class_index)),class_name):continue
            found.append((class_index,self.u32(at+24)))
        if len(found)>1:raise ValueError('Duplicate class definition')
        if not found:return []
        class_index,offset=found[0]
        if not offset:return []
        sizes=[]
        for _ in range(4):
            count,offset=self.uleb(offset)
            if count>100000:raise ValueError('Class data budget')
            sizes.append(count)
        for count in sizes[:2]:
            field_index=0
            for _ in range(count):
                delta,offset=self.uleb(offset);field_index+=delta
                self.entry('fields',field_index)
                _,offset=self.uleb(offset)
        methods=[]
        for count in sizes[2:]:
            index=0
            for n in range(count):
                delta,offset=self.uleb(offset)
                if n and delta==0:raise ValueError('Duplicate encoded method')
                index+=delta
                flags,offset=self.uleb(offset);code,offset=self.uleb(offset)
                at=self.entry('methods',index)
                if self.u16(at)!=class_index:raise ValueError('Method owner mismatch')
                if not flags&0x100:continue
                if code:raise ValueError('Native method has code item')
                methods.append({'name':self.string(self.u32(at+4)),
                    'descriptor':self.descriptor(self.u16(at+2)),
                    'access_flags':flags,'static':bool(flags&8),'method_id':index})
        return methods
