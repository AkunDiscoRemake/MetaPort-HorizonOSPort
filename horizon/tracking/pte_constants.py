"""Recover bounded *serialized* metadata, never execute a getter/model.

Uses ExecuTorch v0.7.0 schema/program.fbs and schema/extended_header.{h,cpp}.
Requires an input-free, instruction-free getter and an immutable byte tensor.
No output here establishes a callable private ABI or camera calibration.
"""
import hashlib
import math
import struct
from horizon.tracking.pte_schema import View

MAX_METADATA=16*1024


def extended_header(data):
    if len(data)<64 or data[8:12]!=b'eh00': raise ValueError('Missing eh00 extended header')
    length,program_size,segment_base=struct.unpack_from('<IQQ',data,12)
    if not 24<=length<=1024 or not 8+length<=program_size<=len(data):
        raise ValueError('Invalid extended header/program size')
    if segment_base and not program_size<=segment_base<=len(data):
        raise ValueError('Invalid segment base')
    return {'header_length':length,'program_size':program_size,'segment_base':segment_base}


def tensor_bytes(data,view,root,tensor,header):
    if view.scalar(tensor,0,'b')!=0 or view.scalar(tensor,1,'i')!=0:
        raise ValueError('Expected zero-offset Byte tensor')
    sizes=view.vector(tensor,2,'i',16)
    if len(sizes)!=1 or not 0<sizes[0]<=MAX_METADATA or view.vector(tensor,3,'B',16)!=[0]:
        raise ValueError('Expected bounded rank-one metadata tensor')
    if view.scalar(tensor,4,'B') or view.field(tensor,6) is not None or view.scalar(tensor,7,'b') or view.scalar(tensor,8,'b'):
        raise ValueError('Mutable, gradient, non-default layout or dynamic tensor')
    extra=view.field(tensor,9)
    if extra is not None and view.scalar(view.ref(extra),2,'B')!=0:
        raise ValueError('External tensor storage unsupported')
    index=view.scalar(tensor,5)
    if index==0: raise ValueError('Not a serialized constant')
    size=sizes[0]
    buffers=view.tables(root,2,10000)
    if buffers:
        if index>=len(buffers): raise ValueError('Constant buffer index')
        raw=bytes(view.vector(buffers[index],0,'B',MAX_METADATA))
        if size>len(raw): raise ValueError('Constant tensor exceeds inline buffer')
        return raw[:size],{'storage':'inline','constant_index':index}
    pos=view.field(root,5)
    if pos is None: raise ValueError('Missing constant segment offsets')
    offsets_table=view.ref(pos)
    segment_index=view.scalar(offsets_table,0)
    offsets=view.vector(offsets_table,1,'Q',100000)
    segments=view.tables(root,4,4096)
    if segment_index>=len(segments) or index>=len(offsets): raise ValueError('Constant segment/index bounds')
    segment=segments[segment_index]
    relative=view.scalar(segment,0,'Q');length=view.scalar(segment,1,'Q')
    base=header['segment_base']
    if not base or relative+length>len(data)-base: raise ValueError('Segment outside model')
    offset=offsets[index]
    next_offset=min((o for o in offsets if o>offset),default=length)
    if offset+size>min(length,next_offset): raise ValueError('Metadata crosses constant boundary')
    start=base+relative+offset
    return data[start:start+size],{'storage':'segment','segment_index':segment_index,
        'constant_index':index,'file_offset':start,'segment_size':length}


def serialized_getter(data,root,name='get_attributes_msgpack'):
    header=extended_header(data)
    # Metadata references must not wander into external tensor/delegate segments.
    view=View(data[:header['program_size']])
    found=[p for p in view.tables(root,1,128) if view.string(p,0)==name]
    if len(found)!=1: raise ValueError('Missing or ambiguous metadata getter')
    plan=found[0]
    if view.vector(plan,3,'i',256): raise ValueError('Getter requires runtime inputs')
    for chain in view.tables(plan,5,256):
        if view.tables(chain,2,16384): raise ValueError('Getter has executable instructions')
    if view.tables(plan,7,256): raise ValueError('Getter declares delegates')
    outputs=view.vector(plan,4,'i',256);values=view.tables(plan,2,10000)
    if len(outputs)!=1 or not 0<=outputs[0]<len(values): raise ValueError('Expected one constant output')
    value=values[outputs[0]]
    if view.scalar(value,0,'B')!=5: raise ValueError('Getter output is not Tensor')
    pos=view.field(value,1)
    if pos is None: raise ValueError('Missing output tensor')
    blob,location=tensor_bytes(data,view,root,view.ref(pos),header)
    return blob,{'method':name,'getter_executed':False,'instruction_count':0,
                 'bytes':len(blob),'sha256':hashlib.sha256(blob).hexdigest(),**location}


def decode_attributes(blob):
    import msgpack
    if len(blob)>MAX_METADATA: raise ValueError('Metadata byte limit')
    # No extension hooks or object construction, and reject duplicate map keys.
    def pairs(items):
        result={}
        for key,value in items:
            if not isinstance(key,str) or key in result: raise ValueError('Invalid/duplicate metadata map key')
            result[key]=value
        return result
    value=msgpack.unpackb(blob,raw=False,strict_map_key=True,object_pairs_hook=pairs,
        max_str_len=MAX_METADATA,max_bin_len=MAX_METADATA,max_array_len=2048,max_map_len=256,max_ext_len=0)
    budget=[0]
    def checked(obj,depth=0):
        budget[0]+=1
        if depth>16 or budget[0]>4096: raise ValueError('Metadata structure budget')
        if isinstance(obj,dict): return {k:checked(v,depth+1) for k,v in obj.items()}
        if isinstance(obj,list): return [checked(v,depth+1) for v in obj]
        if obj is None or isinstance(obj,(str,int,bool)): return obj
        if isinstance(obj,float) and math.isfinite(obj): return obj
        raise ValueError('Unsupported metadata value')
    if not isinstance(value,dict): raise ValueError('Expected attribute map')
    return checked(value)


def inspect_attributes(data,root):
    try:
        blob,evidence=serialized_getter(data,root)
        attributes=decode_attributes(blob)
        return {'status':'SERIALIZED_ATTRIBUTES_RECOVERED','evidence':evidence,'attributes':attributes,
                'semantics_validated_on_camera':False}
    except (ValueError,UnicodeError,ImportError) as error:
        return {'status':'ATTRIBUTES_NOT_RECOVERED','error':str(error)[:300],'getter_executed':False}
