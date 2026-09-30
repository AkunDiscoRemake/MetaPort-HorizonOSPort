import struct
import unittest
from horizon.tracking.pte_schema import View,describe

class Builder:
    def __init__(self):self.data=bytearray(b'\0'*4+b'ET12')
    def align(self):
        while len(self.data)%4:self.data.append(0)
    def table(self,count):
        self.align();vt=len(self.data)
        self.data+=struct.pack('<HH',4+count*2,4+count*4)
        for i in range(count):self.data+=struct.pack('<H',4+i*4)
        self.align();pos=len(self.data)
        self.data+=struct.pack('<i',pos-vt)+bytes(count*4)
        return pos,[pos+4+i*4 for i in range(count)]
    def vector(self,items):
        self.align();pos=len(self.data);self.data+=struct.pack('<I',len(items))
        for item in items:self.data+=struct.pack('<i',item)
        return pos
    def reference(self,pos,target):struct.pack_into('<I',self.data,pos,target-pos)
    def integer(self,pos,n):struct.pack_into('<I',self.data,pos,n)
    def string(self,text):
        self.align();pos=len(self.data);blob=text.encode();self.data+=struct.pack('<I',len(blob))+blob+b'\0';return pos


def fixture():
    b=Builder();root,r=b.table(2);b.integer(0,root);b.integer(r[0],1)
    vec=b.vector([0]);b.reference(r[1],vec)
    plan,p=b.table(8);b.reference(vec+4,plan)
    b.reference(p[0],b.string('forward'))
    # Field 1 omitted container metadata. Vtable slot must be zero for absent field.
    vt=plan-struct.unpack_from('<i',b.data,plan)[0];struct.pack_into('<H',b.data,vt+6,0)
    vals=b.vector([0]);b.reference(p[2],vals)
    value,v=b.table(2);b.reference(vals+4,value);b.integer(v[0],5)
    tensor,t=b.table(4);b.reference(v[1],tensor);b.integer(t[0],6)
    b.reference(t[2],b.vector([1,3,128,128]))
    b.align();order=len(b.data);b.data+=struct.pack('<I',4)+bytes([0,1,2,3]);b.reference(t[3],order)
    b.reference(p[3],b.vector([0]));b.reference(p[4],b.vector([0]))
    b.reference(p[5],b.vector([]));b.reference(p[6],b.vector([]))
    ds=b.vector([0]);b.reference(p[7],ds)
    delegate,d=b.table(1);b.reference(ds+4,delegate);b.reference(d[0],b.string('ExampleBackend'))
    return b,root,p

class SchemaTests(unittest.TestCase):
    def test_tensor_shape_and_delegate_without_loading(self):
        b,root,p=fixture();r=describe(b.data,root)
        self.assertEqual(r['execution_plans'][0]['inputs'][0]['sizes'],[1,3,128,128])
        self.assertEqual(r['execution_plans'][0]['delegates'],['ExampleBackend'])
        self.assertFalse(r['camera_semantics_recovered'])
    def test_bad_index_and_huge_vector(self):
        for count in (999999,):
            b,root,p=fixture();start=View(b.data).ref(p[3]);b.integer(start,count)
            with self.assertRaises(ValueError):describe(b.data,root)
        b,root,p=fixture();start=View(b.data).ref(p[3]);b.integer(start+4,99)
        with self.assertRaises(ValueError):describe(b.data,root)
    def test_missing_and_out_of_bounds_reference(self):
        b,root,p=fixture();b.integer(p[0],0)
        with self.assertRaises(ValueError):describe(b.data,root)
        b,root,p=fixture();b.integer(p[0],0x7fffffff)
        with self.assertRaises(ValueError):describe(b.data,root)

    def test_delegate_instruction_references_not_just_strings(self):
        b,root,p=fixture()
        cv=b.vector([0]);b.reference(p[5],cv)
        chain,ch=b.table(3);b.reference(cv+4,chain)
        b.reference(ch[0],b.vector([0]));b.reference(ch[1],b.vector([0]))
        iv=b.vector([0]);b.reference(ch[2],iv)
        instruction,ins=b.table(2);b.reference(iv+4,instruction);b.integer(ins[0],2)
        call,ca=b.table(2);b.reference(ins[1],call);b.integer(ca[0],0)
        b.reference(ca[1],b.vector([0]))
        r=describe(b.data,root)['execution_plans'][0]
        self.assertEqual(r['delegate_call_sites'][0]['backend'],'ExampleBackend')
        self.assertFalse(r['control_flow_evaluated'])
        b.integer(ca[0],99)
        with self.assertRaises(ValueError):describe(b.data,root)

    def test_repeated_aliases_cannot_bypass_global_budget(self):
        b,root,p=fixture();view=View(b.data)
        view.cells=249999
        with self.assertRaisesRegex(ValueError,'Aggregate traversal'):
            view.vector(root,1);view.vector(root,1)
