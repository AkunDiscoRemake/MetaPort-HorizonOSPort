"""Read-only bounded view of selected ExecuTorch v0.7 Program schema fields.

Reference: pytorch/executorch schema/program.fbs, v0.7.0,
Git blob 7308cc631994146e037b7a88749aa4c8e87fe93a (BSD-3-Clause).
This reference is NOT established as the exact private firmware schema.
Unknown union alternatives stay opaque. No operators/delegates are loaded.
"""
import struct


class View:
    def __init__(self,data): self.data=data
    def read(self,fmt,offset):
        size=struct.calcsize('<'+fmt)
        if offset<0 or offset+size>len(self.data): raise ValueError('Out-of-bounds scalar')
        return struct.unpack_from('<'+fmt,self.data,offset)[0]
    def field(self,table,index,width=4):
        vt=table-self.read('i',table)
        if vt<8: raise ValueError('Invalid vtable')
        size=self.read('H',vt);obj=self.read('H',vt+2)
        if size<4 or size%2 or vt+size>len(self.data) or obj<4 or table+obj>len(self.data):
            raise ValueError('Invalid table extent')
        if 4+index*2>=size: return None
        off=self.read('H',vt+4+index*2)
        if not off: return None
        if off<4 or off+width>obj: raise ValueError('Field exceeds object')
        return table+off
    def ref(self,offset):
        relative=self.read('I',offset)
        target=offset+relative
        if relative<4 or target>=len(self.data): raise ValueError('Invalid forward reference')
        return target
    def scalar(self,table,index,fmt='I'):
        pos=self.field(table,index,struct.calcsize('<'+fmt))
        return self.read(fmt,pos) if pos is not None else 0
    def vector(self,table,index,fmt='I',limit=4096):
        pos=self.field(table,index)
        if pos is None: return []
        start=self.ref(pos);count=self.read('I',start);size=struct.calcsize('<'+fmt)
        if count>limit or start+4+count*size>len(self.data): raise ValueError('Vector bounds/limit')
        return [self.read(fmt,start+4+i*size) for i in range(count)]
    def tables(self,table,index,limit=4096):
        pos=self.field(table,index)
        if pos is None: return []
        start=self.ref(pos);count=self.read('I',start)
        if count>limit or start+4+count*4>len(self.data): raise ValueError('Table vector bounds/limit')
        return [self.ref(start+4+i*4) for i in range(count)]
    def string(self,table,index):
        pos=self.field(table,index)
        if pos is None: return None
        start=self.ref(pos);size=self.read('I',start)
        if size>512 or start+4+size>=len(self.data) or self.data[start+4+size]!=0:
            raise ValueError('String bounds/termination')
        text=self.data[start+4:start+4+size].decode('utf-8')
        if any(ord(c)<32 for c in text): raise ValueError('Control characters in identifier')
        return text
    def value(self,values,index):
        if not 0<=index<len(values): raise ValueError('EValue index out of range')
        obj=values[index];tag=self.scalar(obj,0,'B')
        result={'value_index':index,'kernel_union_tag':tag}
        if tag==5: # KernelTypes.Tensor in the pinned public schema.
            pos=self.field(obj,1)
            if pos is None: raise ValueError('Missing tensor union payload')
            tensor=self.ref(pos)
            sizes=self.vector(tensor,2,'i',16);order=self.vector(tensor,3,'B',16)
            if any(d<0 for d in sizes): raise ValueError('Negative tensor dimension')
            if sorted(order)!=list(range(len(sizes))): raise ValueError('Invalid dimension permutation')
            result.update(kind='Tensor',scalar_type_code=self.scalar(tensor,0,'b'),
                          sizes=sizes,dim_order=order)
        else: result['kind']='OPAQUE_UNION_ALTERNATIVE'
        return result


def describe(data,root):
    view=View(data);plans=[]
    for plan in view.tables(root,1,128):
        values=view.tables(plan,2,10000)
        inputs=view.vector(plan,3,'i',256);outputs=view.vector(plan,4,'i',256)
        operators=[{'name':view.string(t,0),'overload':view.string(t,1)} for t in view.tables(plan,6)]
        delegates=[view.string(t,0) for t in view.tables(plan,7,256)]
        plans.append({'name':view.string(plan,0),'inputs':[view.value(values,i) for i in inputs],
                      'outputs':[view.value(values,i) for i in outputs],
                      'operators':operators,'delegates':delegates})
    if not plans or any(not p['name'] for p in plans): raise ValueError('Missing execution plan/name')
    return {'interpretation':'PUBLIC_SCHEMA_CANDIDATE_NOT_RUNTIME_VALIDATED',
            'schema_reference':'pytorch/executorch v0.7.0 schema/program.fbs',
            'schema_git_blob':'7308cc631994146e037b7a88749aa4c8e87fe93a',
            'serialized_program_version':view.scalar(root,0),'execution_plans':plans,
            'all_instructions_validated':False,'camera_semantics_recovered':False}
