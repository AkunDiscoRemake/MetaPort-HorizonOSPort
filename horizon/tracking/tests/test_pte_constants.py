import importlib.util
import struct
import unittest
from horizon.tracking.pte_constants import serialized_getter,decode_attributes,extended_header


class Builder:
    def __init__(self): self.data=bytearray(64);self.data[4:8]=b'ET12';self.data[8:12]=b'eh00'
    def align(self,n=8):
        while len(self.data)%n:self.data.append(0)
    def table(self,n):
        self.align();vt=len(self.data);self.data+=struct.pack('<HH',4+2*n,8+8*n)+bytes(2*n)
        self.align();pos=len(self.data);self.data+=struct.pack('<i',pos-vt)+bytes(4+8*n)
        return pos,vt
    def field(self,t,i):
        struct.pack_into('<H',self.data,t[1]+4+2*i,8+8*i)
        return t[0]+8+8*i
    def scalar(self,t,i,v,fmt='I'):struct.pack_into('<'+fmt,self.data,self.field(t,i),v)
    def ref(self,t,i,target):
        pos=self.field(t,i);struct.pack_into('<I',self.data,pos,target-pos)
    def vector(self,items,fmt='I'):
        self.align();self.data+=bytes(4) # 64-bit payload alignment
        pos=len(self.data);self.data+=struct.pack('<I',len(items))
        for value in items:self.data+=struct.pack('<'+fmt,value)
        return pos
    def tabvec(self,t,i):
        vec=self.vector([0]);self.ref(t,i,vec);return vec+4
    def item(self,pos,t):struct.pack_into('<I',self.data,pos,t[0]-pos)
    def string(self,text):
        self.align();pos=len(self.data);raw=text.encode();self.data+=struct.pack('<I',len(raw))+raw+b'\0';return pos


def fixture(inline=False):
    raw=b'\x82\xa6height\x60\xa5views\x02'
    b=Builder();root=b.table(6);struct.pack_into('<I',b.data,0,root[0]);b.scalar(root,0,1)
    pv=b.tabvec(root,1);plan=b.table(8);b.item(pv,plan)
    b.ref(plan,0,b.string('get_attributes_msgpack'))
    vv=b.tabvec(plan,2);val=b.table(2);b.item(vv,val);b.scalar(val,0,5,'B')
    tensor=b.table(10);b.ref(val,1,tensor[0])
    b.ref(tensor,2,b.vector([len(raw)],'i'));b.ref(tensor,3,b.vector([0],'B'));b.scalar(tensor,5,1)
    b.ref(plan,4,b.vector([0],'i'))
    if inline:
        vec=b.vector([0,0]);b.ref(root,2,vec)
        empty=b.table(1);b.item(vec+4,empty)
        buf=b.table(1);b.item(vec+8,buf);b.ref(buf,0,b.vector(raw,'B'))
    else:
        sv=b.tabvec(root,4);segment=b.table(2);b.item(sv,segment);b.scalar(segment,1,8+len(raw),'Q')
        offsets=b.table(2);b.ref(root,5,offsets[0]);b.ref(offsets,1,b.vector([0,8],'Q'))
    program_size=len(b.data);base=0
    if not inline:
        b.align(64);base=len(b.data);b.data+=bytes(8)+raw
    struct.pack_into('<IQQ',b.data,12,24,program_size,base)
    return b,root,plan,tensor,raw


class ConstantTests(unittest.TestCase):
    def test_inline_and_segment_bytes_without_execution(self):
        for inline in (False,True):
            b,root,plan,tensor,raw=fixture(inline)
            blob,evidence=serialized_getter(b.data,root[0])
            self.assertEqual(blob,raw);self.assertFalse(evidence['getter_executed'])
            self.assertEqual(evidence['storage'],'inline' if inline else 'segment')

    def test_mutable_and_dynamic_tensor_rejected(self):
        for field in (4,8):
            b,root,plan,tensor,raw=fixture();b.scalar(tensor,field,1,'B')
            with self.assertRaises(ValueError):serialized_getter(b.data,root[0])
        b,root,plan,tensor,raw=fixture();b.scalar(tensor,5,0)
        with self.assertRaises(ValueError):serialized_getter(b.data,root[0])

    def test_getter_inputs_instructions_and_ambiguous_outputs_rejected(self):
        for field in (3,4):
            b,root,plan,tensor,raw=fixture(True)
            b.ref(plan,field,b.vector([0,0],'i'))
            struct.pack_into('<Q',b.data,16,len(b.data))
            with self.assertRaises(ValueError):serialized_getter(b.data,root[0])
        b,root,plan,tensor,raw=fixture(True)
        cv=b.tabvec(plan,5);chain=b.table(3);b.item(cv,chain)
        iv=b.tabvec(chain,2);instruction=b.table(2);b.item(iv,instruction)
        struct.pack_into('<Q',b.data,16,len(b.data))
        with self.assertRaisesRegex(ValueError,'executable instructions'):serialized_getter(b.data,root[0])

    def test_external_allocation_and_ambiguous_storage_rejected(self):
        b,root,plan,tensor,raw=fixture(True)
        extra=b.table(3);b.ref(tensor,9,extra[0]);b.scalar(extra,2,1,'B')
        struct.pack_into('<Q',b.data,16,len(b.data))
        with self.assertRaisesRegex(ValueError,'External'):serialized_getter(b.data,root[0])
        b,root,plan,tensor,raw=fixture();b.scalar(tensor,6,4)
        with self.assertRaisesRegex(ValueError,'Mutable'):serialized_getter(b.data,root[0])
        b,root,plan,tensor,raw=fixture(True)
        offsets=b.table(2);b.ref(root,5,offsets[0]);b.ref(offsets,1,b.vector([0,8],'Q'))
        struct.pack_into('<Q',b.data,16,len(b.data))
        with self.assertRaisesRegex(ValueError,'Ambiguous'):serialized_getter(b.data,root[0])

    def test_segment_and_header_bounds(self):
        b,root,plan,tensor,raw=fixture()
        with self.assertRaises(ValueError):serialized_getter(b.data[:-1],root[0])
        struct.pack_into('<Q',b.data,24,1)
        with self.assertRaises(ValueError):extended_header(b.data)

    @unittest.skipUnless(importlib.util.find_spec('msgpack'),'optional msgpack dependency')
    def test_messagepack_limits_duplicates_and_no_hooks(self):
        b,root,plan,tensor,raw=fixture()
        self.assertEqual(decode_attributes(raw),{'height':96,'views':2})
        for bad in (b'\x82\xa1a\x01\xa1a\x02',b'\x81\x01\x01',b'\xd4\x01\x00',b'\x91\x00'):
            with self.assertRaises(ValueError):decode_attributes(bad)
