# SPDX-License-Identifier: GPL-3.0-only
"""Lossless preparation of original hand geometry, NOT a tracking/animation runtime.

Preserves winding, UV seams, all skin influences and source vertex identity.
No guessed units, quaternion order, bone retargeting, triangulation or weight pruning.
Generated proprietary-derived buffers stay in the ignored analysis workspace.
"""
import argparse
from collections import Counter
import hashlib
import json
import math
import os
from pathlib import Path
import struct
import tempfile

from horizon.tracking.inspect_original import BUILD, digest
from tools.scan_partitions import dump_entry

MAX_BYTES = 512 * 1024
ROOT = (1 << 64) - 1


def decode(raw):
    import msgpack
    if not 0 < len(raw) <= MAX_BYTES:
        raise ValueError('Asset byte limit')
    def pairs(items):
        out = {}
        for key, value in items:
            if not isinstance(key, str) or key in out:
                raise ValueError('Invalid or duplicate map key')
            out[key] = value
        return out
    obj = msgpack.unpackb(raw, raw=False, strict_map_key=True, object_pairs_hook=pairs,
                         max_array_len=100000, max_map_len=256, max_str_len=4096,
                         max_bin_len=0, max_ext_len=0)
    budget = [0]
    def check(value, depth=0):
        budget[0] += 1
        if depth > 32 or budget[0] > 200000:
            raise ValueError('Asset structure limit')
        if isinstance(value, dict):
            for item in value.values(): check(item, depth+1)
        elif isinstance(value, list):
            for item in value: check(item, depth+1)
        elif type(value) in (str, int, bool) or value is None:
            pass
        elif type(value) is float and math.isfinite(value):
            pass
        else:
            raise ValueError('Unsupported or nonfinite asset value')
    check(obj)
    return obj


def integer(value, limit):
    if type(value) is not int or not 0 <= value < limit:
        raise ValueError('Index out of range')
    return value


def number(value):
    if type(value) not in (float, int) or not math.isfinite(value):
        raise ValueError('Expected finite number')
    return value


def vector(value, width):
    if not isinstance(value, list) or len(value) != width:
        raise ValueError('Vector shape')
    return [number(x) for x in value]


def f32(value):
    value = number(value)
    try: raw = struct.pack('<f', value)
    except (OverflowError, struct.error): raise ValueError('Not representable in float32')
    if struct.unpack('<f', raw)[0] != value:
        raise ValueError('Refuse lossy float32 conversion')
    return raw


def offsets(values, count, end):
    if count < 1 or end < 0 or not isinstance(values, list) or len(values) != count+1:
        raise ValueError('Offset count')
    for x in values: integer(x, end+1)
    if values[0] != 0 or values[-1] != end or any(a > b for a,b in zip(values,values[1:])):
        raise ValueError('Invalid CSR offsets')
    return values


def skeleton_order(bones):
    if not isinstance(bones, list) or not 0 < len(bones) <= 512:
        raise ValueError('Bone count')
    names, children, roots = set(), [[] for _ in bones], []
    for index, bone in enumerate(bones):
        name = bone['Name']
        if not isinstance(name,str) or not name or name in names:
            raise ValueError('Bone name missing or duplicated')
        names.add(name)
        parent = bone['Parent']
        if type(parent) is not int: raise ValueError('Parent type')
        if parent == ROOT: roots.append(index)
        else: children[integer(parent,len(bones))].append(index)
        vector(bone['PreRotation'],4)
        vector(bone['TranslationOffset'],3)
        if not isinstance(bone['RestState'],dict): raise ValueError('Rest state shape')
    order = list(roots)
    for parent in order: order.extend(children[parent])
    if len(order) != len(bones): raise ValueError('Cyclic or rootless skeleton')
    return order


def compile_mesh(asset):
    """Internal portable buffer layout; never exported as an original private ABI."""
    mesh, bones = asset['skinnedmodel'], asset['skeleton']['Bones']
    order = skeleton_order(bones)
    if type(mesh['NumberOfBones']) is not int or mesh['NumberOfBones'] != len(bones):
        raise ValueError('Mesh/skeleton bone count mismatch')
    positions, normals, uv = mesh['RestPositions'], mesh['RestVertexNormals'], mesh['TextureCoordinates']
    if not 0 < len(positions) <= 100000 or len(normals) != len(positions) or not 0 < len(uv) <= 100000:
        raise ValueError('Vertex array count')
    for rows, width in ((positions,3),(normals,3),(uv,2)):
        for row in rows: vector(row,width)
    faces = mesh['Faces']; indices, tex = faces['Indices'], faces['TextureIndices']
    if not indices or len(indices) > 100000 or len(tex) != len(indices): raise ValueError('Corner count')
    face_offsets = offsets(faces['Offsets'],len(faces['Offsets'])-1,len(indices))
    if any(b-a != 3 for a,b in zip(face_offsets,face_offsets[1:])):
        raise ValueError('Only original triangles; no guessed triangulation')
    weights = mesh['SkinningWeights']
    skin_offsets = offsets(mesh['SkinningOffsets'],len(positions),len(weights))
    # Keep hierarchy intact; only compact the palette addressed by skin weights.
    palette = sorted({integer(item[0],len(bones)) for item in weights
                      if isinstance(item,list) and len(item)==2})
    palette_index = {bone:index for index,bone in enumerate(palette)}
    packed_weights = bytearray(); sums = []; influence_counts = []
    for item in weights:
        if not isinstance(item,list) or len(item) != 2: raise ValueError('Influence shape')
        bone, weight = integer(item[0],len(bones)), number(item[1])
        if weight < 0: raise ValueError('Negative skin weight')
        packed_weights += struct.pack('<I',palette_index[bone])+f32(weight)
    for a,b in zip(skin_offsets,skin_offsets[1:]):
        if a == b: raise ValueError('Unweighted vertex')
        sums.append(math.fsum(w[1] for w in weights[a:b])); influence_counts.append(b-a)
    # Identity, not float-value welding: coincident vertices may have different skinning.
    unique = {}; sources = []; corners = []; packed_vertices = bytearray()
    for vertex, texture in zip(indices,tex):
        vertex, texture = integer(vertex,len(positions)), integer(texture,len(uv))
        key = (vertex,texture)
        if key not in unique:
            unique[key] = len(unique); sources.append(vertex)
            for value in positions[vertex]+normals[vertex]+uv[texture]: packed_vertices += f32(value)
        corners.append(unique[key])
    fmt = 'H' if len(unique) <= 65536 else 'I'
    streams = {'bone_palette':struct.pack('<'+'I'*len(palette),*palette),
               'vertices': bytes(packed_vertices),
               'indices': struct.pack('<'+fmt*len(corners),*corners),
               'vertex_sources': struct.pack('<'+'I'*len(sources),*sources),
               'skinning_offsets': struct.pack('<'+'I'*len(skin_offsets),*skin_offsets),
               'skinning_weights': bytes(packed_weights)}
    summary = {'source_vertices':len(positions),'draw_vertices':len(unique),'corners':len(corners),
               'triangles':len(corners)//3,'bones':len(bones),'hierarchy_order':order,
               'palette_bones':len(palette),'skinning_index_space':'compact_palette',
               'index_bits':16 if fmt=='H' else 32,'vertex_stride_bytes':32,
               'influence_histogram':dict(sorted(Counter(influence_counts).items())),
               'max_weight_sum_error':max(abs(s-1) for s in sums),
               'weights_normalized':False,'influences_pruned':False,
               'unindexed_vertex_bytes':len(corners)*32,'indexed_vertex_bytes':len(packed_vertices),
               'unit_conversion_applied':False,'coordinate_conversion_applied':False,
               'animation_mapping_validated':False,'renderer_integrated':False,
               'streams':{k:{'size_bytes':len(v),'sha256':hashlib.sha256(v).hexdigest()} for k,v in streams.items()}}
    return streams, summary


def validate_streams(asset, streams, summary):
    """Independent decode/compare of all corners and influences, not runtime proof."""
    mesh=asset['skinnedmodel']; corners=mesh['Faces']['Indices']
    if summary['index_bits'] not in (16,32): raise ValueError('Index representation')
    fmt='H' if summary['index_bits']==16 else 'I'
    def unpack(name,code,width):
        data=streams[name]
        if len(data)%width: raise ValueError('Stream alignment')
        return struct.unpack('<'+code*(len(data)//width),data)
    indices=unpack('indices',fmt,summary['index_bits']//8)
    sources=unpack('vertex_sources','I',4); palette=unpack('bone_palette','I',4)
    if len(indices)!=len(corners) or len(streams['vertices'])!=32*len(sources):
        raise ValueError('Stream counts')
    if len(sources)!=summary['draw_vertices'] or len(palette)!=summary['palette_bones']:
        raise ValueError('Summary counts')
    for n,index in enumerate(indices):
        integer(index,len(sources));vertex=corners[n]
        if sources[index]!=vertex: raise ValueError('Source identity changed')
        actual=struct.unpack_from('<8f',streams['vertices'],32*index)
        expected=mesh['RestPositions'][vertex]+mesh['RestVertexNormals'][vertex]+mesh['TextureCoordinates'][mesh['Faces']['TextureIndices'][n]]
        # Numeric == hides signed-zero changes. Compare decoded double representations.
        if any(struct.pack('<d',float(a)) != struct.pack('<d',b) for a,b in zip(expected,actual)):
            raise ValueError('Corner geometry changed')
    if tuple(mesh['SkinningOffsets'])!=unpack('skinning_offsets','I',4):
        raise ValueError('Skinning offsets changed')
    weights=streams['skinning_weights']
    if len(weights)!=8*len(mesh['SkinningWeights']):raise ValueError('Influence count changed')
    for n,(bone,weight) in enumerate(mesh['SkinningWeights']):
        index,value=struct.unpack_from('<If',weights,n*8)
        integer(index,len(palette))
        if palette[index]!=bone or struct.pack('<d',value)!=struct.pack('<d',float(weight)):
            raise ValueError('Skinning influence changed')
    return {'all_corners_equal':True,'all_influences_equal':True,
            'source_vertex_identity_preserved':True,'runtime_equivalence_established':False}


def inspect(images, reconstruction, output):
    output.mkdir(parents=True,exist_ok=True)
    image = images/'odm.img'; expected=json.loads(reconstruction.read_text())['partitions']['odm']
    if not expected['sha256_match'] or image.stat().st_size != expected['size_bytes'] or digest(image)!=expected['sha256']:
        raise ValueError('Unverified ODM')
    policy=json.loads(Path('horizon/tracking/hand-assets-policy.json').read_text())
    inventory=json.loads(Path(f'analysis/builds/{BUILD}/static-analysis.json').read_text())['partitions']['odm']['entries']
    report={'build':BUILD,'source_commit':os.environ.get('GITHUB_SHA'),
            'workflow_run':os.environ.get('GITHUB_RUN_ID'),'source_image_sha256':expected['sha256'],'firmware_executed':False,
            'hand_tracking_ported':False,'phone_performance_measured':False,'assets':[]}
    for row in policy['assets']:
        matches=[e for e in inventory if e['kind']=='file' and e['path']==row['path']]
        if len(matches)!=1: raise ValueError('Missing/duplicate inventory asset')
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'asset';dump_entry(image,matches[0],path)
            if path.stat().st_size != row['size'] or digest(path)!=row['sha256']:
                raise ValueError('Wrong fixed-build hand asset')
            obj=decode(path.read_bytes()); item=dict(row)
            if 'skinnedmodel' in obj:
                streams, details=compile_mesh(obj)
                item['roundtrip_validation']=validate_streams(obj,streams,details)
                # Buffers are local only; workflow publishes summary JSON, not these assets.
                for name,data in streams.items(): (output/(Path(row['path']).stem+'.'+name+'.bin')).write_bytes(data)
                item['geometry']=details
                item['bone_metadata']=[{'name':b['Name'],'parent':b['Parent'],'joint_type':b['JointType'],
                                       'rotation_order':b['RotationOrder'],'rest_state_fields':sorted(b['RestState'])}
                                      for b in obj['skeleton']['Bones']]
            elif isinstance(obj,dict) and 'poseLibrary' in obj:
                joints=obj['handModel']['joints']; poses=obj['poseLibrary']
                for pose in poses:
                    if not isinstance(pose,list) or len(pose)!=2 or not isinstance(pose[0],str):
                        raise ValueError('Pose library entry')
                    vector(pose[1],len(joints))
                item['pose_library']={'poses':len(poses),'channels':len(joints),
                    'channel_names':[j['name'] for j in joints], 'timeline_or_fps_established':False,
                    'render_bone_mapping_established':False}
            else:
                if not isinstance(obj,list): raise ValueError('Rest skeleton collection')
                item['rest_skeletons']=[{'bones':len(x['bones']),'joints':len(x['joints']),
                                          'limits':len(x['jalimits']),'header':x['header']} for x in obj]
            report['assets'].append(item)
    (output/'hand-assets-report.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
    return report


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('images','reconstruction','output'):p.add_argument('--'+name,required=True,type=Path)
    a=p.parse_args();inspect(a.images,a.reconstruction,a.output)
