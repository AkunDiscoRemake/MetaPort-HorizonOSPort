"""Bounded, offline exploration of this build's etz0 deflate containers.

Not a universal PTEZ loader. Never loads operators, tensors, pickle or guest code.
Accept only a unique complete stream, declared length and an ExecuTorch identifier.
Offsets/wbits are measured evidence, not assumed from the filename.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import struct
import zlib
from horizon.tracking.inspect_original import digest, BUILD
from tools.scan_partitions import dump_entry

MAX_INPUT=32*1024*1024
MAX_OUTPUT=64*1024*1024


def pte_header(data):
    if len(data)<16 or not re.fullmatch(rb'ET[0-9]{2}',data[4:8]):
        raise ValueError('Not an identified ExecuTorch FlatBuffer')
    root=struct.unpack_from('<I',data)[0]
    if root<8 or root+4>len(data) or root%4:
        raise ValueError('Invalid FlatBuffer root offset')
    # FlatBuffer tables begin with a signed offset to a bounded vtable.
    distance=struct.unpack_from('<i',data,root)[0]
    vtable=root-distance
    if not distance or vtable<8 or vtable+4>len(data): raise ValueError('Invalid vtable offset')
    size,object_size=struct.unpack_from('<HH',data,vtable)
    if size<4 or size%2 or vtable+size>len(data) or object_size<4 or root+object_size>len(data):
        raise ValueError('Invalid FlatBuffer table bounds')
    for field in struct.unpack_from('<'+'H'*((size-4)//2),data,vtable+4):
        if field and not 4<=field<object_size: raise ValueError('Field outside table')
    return {'identifier':data[4:8].decode(),'root_offset':root,'vtable_offset':vtable,
            'vtable_bytes':size,'root_object_bytes':object_size,
            'qualification':'Root structure only; not full schema or model execution validation.'}


def inspect_container(blob):
    if not 24<=len(blob)<=MAX_INPUT: raise ValueError('Container size limit')
    if blob[:4]!=b'etz0': raise ValueError('Unsupported container magic')
    header_size,declared=struct.unpack_from('<IQ',blob,4)
    if header_size!=24 or blob[16:24]!=b'deflate\0': raise ValueError('Unsupported etz0 header')
    if not 16<=declared<=MAX_OUTPUT: raise ValueError('Declared output size limit')
    # Explicit small search domain; do not blindly inflate every byte of model weights.
    candidates={24,32,64,128,256,512,1024,2048,4096,8192}
    first=next((i for i in range(24,min(len(blob),65536)) if blob[i]),None)
    if first is not None: candidates.update((first,max(24,first-1)))
    successes=[];attempts=[]
    for offset in sorted(candidates):
        if offset>=len(blob) or any(blob[24:offset]): continue
        for wbits in (15,-15):
            try:
                decoder=zlib.decompressobj(wbits)
                raw=decoder.decompress(blob[offset:],declared+1)
                if len(raw)!=declared or not decoder.eof or decoder.unconsumed_tail or decoder.unused_data:
                    raise ValueError('Incomplete stream, wrong length or trailing data')
                header=pte_header(raw)
                successes.append((offset,wbits,raw,header))
            except (zlib.error,ValueError) as error:
                attempts.append({'offset':offset,'wbits':wbits,'error':str(error)[:120]})
    base={'declared_output_bytes':declared,'source_sha256':hashlib.sha256(blob).hexdigest(),
          'firmware_executed':False,'inference_tested':False,'attempts':attempts}
    if len(successes)!=1:
        return {**base,'status':'NO_UNIQUE_VALIDATED_STREAM','candidate_count':len(successes),
                'prefix_hex':blob[:256].hex()},None
    offset,wbits,raw,header=successes[0]
    strings=sorted(set(m.group().decode('ascii') for m in re.finditer(rb'[A-Za-z_][A-Za-z0-9_:. /-]{5,180}',raw)
        if re.search(rb'boltnn|backend|forward|Xnnpack|Qnn|Hexagon|aten::',m.group(),re.I)))[:256]
    return {**base,'status':'DECOMPRESSED_STRUCTURAL_ONLY','payload_offset':offset,'zlib_wbits':wbits,
            'decoded_sha256':hashlib.sha256(raw).hexdigest(),'decoded_size':len(raw),
            'pte_header':header,'backend_strings_sample':strings},raw


def inspect(images,reconstruction,output):
    image=Path(images)/'odm.img';output=Path(output);output.mkdir(parents=True,exist_ok=True)
    expected=json.loads(Path(reconstruction).read_text())['partitions']['odm']['sha256']
    if digest(image)!=expected: raise ValueError('Partition hash mismatch')
    entries=json.loads(Path(f'analysis/builds/{BUILD}/static-analysis.json').read_text())['partitions']['odm']['entries']
    selected=[e for e in entries if e['kind']=='file' and e['path'].startswith('/etc/handtracking/') and e['path'].endswith('.ptez')]
    report={'build':BUILD,'models_executed':False,'models':[]}
    import tempfile
    for entry in selected:
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'model';dump_entry(image,entry,path)
            result,raw=inspect_container(path.read_bytes())
            report['models'].append({'path':entry['path'],**result})
            # Decoded proprietary models remain runner-local, never in Git/artifacts.
            if raw is not None: (output/(Path(entry['path']).stem+'.pte')).write_bytes(raw)
    (output/'ptez-report.json').write_text(json.dumps(report,indent=2)+'\n')


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('images','reconstruction','output'): p.add_argument('--'+name,required=True)
    a=p.parse_args();inspect(a.images,a.reconstruction,a.output)
