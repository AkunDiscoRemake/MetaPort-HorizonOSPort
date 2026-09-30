# SPDX-License-Identifier: GPL-3.0-only
import copy
import struct
import unittest
from horizon.tracking.hand_assets import compile_mesh, decode, ROOT, skeleton_order


def fixture():
    bone={'Name':'root','Parent':ROOT,'PreRotation':[0.,0.,0.,1.],
          'TranslationOffset':[0.,0.,0.],'RestState':{},'RotationOrder':'XYZ','JointType':'Limb'}
    return {'skeleton':{'Bones':[bone]},'skinnedmodel':{
        'NumberOfBones':1,'RestPositions':[[0.,0.,0.],[1.,0.,0.],[0.,1.,0.]],
        'RestVertexNormals':[[0.,0.,1.]]*3,'TextureCoordinates':[[0.,0.],[1.,0.],[0.,1.],[.5,.5]],
        'Faces':{'Indices':[0,1,2,0,2,1], 'TextureIndices':[0,1,2,3,2,1], 'Offsets':[0,3,6]},
        'SkinningOffsets':[0,1,2,3],'SkinningWeights':[[0,1.]]*3}}


class HandAssetTests(unittest.TestCase):
    def test_seams_winding_and_source_identity_are_preserved(self):
        asset=fixture(); before=copy.deepcopy(asset)
        streams,report=compile_mesh(asset)
        self.assertEqual(asset,before)
        self.assertEqual(report['draw_vertices'],4)
        self.assertEqual(struct.unpack('<6H',streams['indices']),(0,1,2,3,2,1))
        self.assertEqual(struct.unpack('<4I',streams['vertex_sources']),(0,1,2,0))
        self.assertEqual(report['indexed_vertex_bytes'],128)
        self.assertEqual(report['unindexed_vertex_bytes'],192)
        self.assertFalse(report['animation_mapping_validated'])
        # Reconstruct EVERY corner, not just counts, to check lossless reindexing.
        ids=struct.unpack('<6H',streams['indices'])
        for c,idx in enumerate(ids):
            m=asset['skinnedmodel']; v=m['Faces']['Indices'][c]; t=m['Faces']['TextureIndices'][c]
            original=m['RestPositions'][v]+m['RestVertexNormals'][v]+m['TextureCoordinates'][t]
            self.assertEqual(list(struct.unpack_from('<8f',streams['vertices'],idx*32)),original)

    def test_coincident_positions_not_welded(self):
        a=fixture();a['skinnedmodel']['RestPositions'][1]=[0.,0.,0.]
        _,r=compile_mesh(a);self.assertEqual(r['draw_vertices'],4)

    def test_weights_never_pruned_or_normalized(self):
        a=fixture();a['skinnedmodel']['SkinningOffsets']=[0,5,6,7]
        a['skinnedmodel']['SkinningWeights']=[[0,.125]]*5+[[0,1.],[0,1.]]
        streams,r=compile_mesh(a)
        self.assertEqual(r['influence_histogram'],{1:2,5:1})
        self.assertEqual(r['max_weight_sum_error'],.375)
        self.assertEqual(len(streams['skinning_weights']),56)

    def test_reject_invalid_geometry_without_repair(self):
        mutations=[lambda m:m['Faces']['Indices'].__setitem__(0,-1),
                   lambda m:m['Faces']['TextureIndices'].__setitem__(0,100),
                   lambda m:m['Faces'].__setitem__('Offsets',[0,4,6]),
                   lambda m:m['SkinningOffsets'].__setitem__(1,9),
                   lambda m:m['SkinningWeights'].__setitem__(0,[1,1.]),
                   lambda m:m['SkinningWeights'].__setitem__(0,[0,-1.]),
                   lambda m:m['RestPositions'][0].__setitem__(0,float('nan')),
                   lambda m:m['RestPositions'][0].__setitem__(0,0.1),
                   lambda m:m.__setitem__('NumberOfBones',True)]
        for mutation in mutations:
            a=fixture();mutation(a['skinnedmodel'])
            with self.assertRaises(ValueError):compile_mesh(a)

    def test_hierarchy_order_and_cycles(self):
        root=fixture()['skeleton']['Bones'][0];child=copy.deepcopy(root)
        child.update(Name='child',Parent=1)
        self.assertEqual(skeleton_order([child,root]),[1,0])
        child['Parent']=0
        with self.assertRaises(ValueError):skeleton_order([child,root])

    def test_messagepack_rejects_duplicates_extensions_nonfinite_and_limits(self):
        import msgpack
        self.assertEqual(decode(msgpack.packb(fixture(),use_bin_type=True)),fixture())
        for raw in (b'\x82\xa1a\x01\xa1a\x02',msgpack.packb(float('inf')),
                    msgpack.packb(msgpack.ExtType(1,b'x')),b'x'*(512*1024+1)):
            with self.assertRaises((ValueError,msgpack.UnpackException)):decode(raw)

    def test_palette_compaction_keeps_original_bone_identity(self):
        from horizon.tracking.hand_assets import validate_streams
        a=fixture();root=a['skeleton']['Bones'][0]
        child=copy.deepcopy(root);child.update(Name='child',Parent=0)
        a['skeleton']['Bones'].append(child);a['skinnedmodel']['NumberOfBones']=2
        a['skinnedmodel']['SkinningWeights']=[[1,1.]]*3
        streams,summary=compile_mesh(a)
        self.assertEqual(summary['palette_bones'],1)
        self.assertEqual(streams['bone_palette'],struct.pack('<I',1))
        self.assertTrue(validate_streams(a,streams,summary)['all_influences_equal'])
        streams['bone_palette']=struct.pack('<I',0)
        with self.assertRaises(ValueError):validate_streams(a,streams,summary)

    def test_roundtrip_detects_corrupt_corner_and_offset_streams(self):
        from horizon.tracking.hand_assets import validate_streams
        a=fixture();streams,summary=compile_mesh(a)
        for key in ('vertices','indices','vertex_sources','skinning_offsets','skinning_weights'):
            bad=dict(streams);data=bytearray(bad[key]);data[0]^=1;bad[key]=bytes(data)
            with self.assertRaises(ValueError):validate_streams(a,bad,summary)

    def test_signed_zero_corruption_and_empty_offsets_are_rejected(self):
        from horizon.tracking.hand_assets import validate_streams
        a=fixture();streams,summary=compile_mesh(a)
        corrupt=bytearray(streams['vertices']);corrupt[3]^=0x80
        streams['vertices']=bytes(corrupt)
        with self.assertRaises(ValueError):validate_streams(a,streams,summary)
        a['skinnedmodel']['Faces']['Offsets']=[]
        with self.assertRaises(ValueError):compile_mesh(a)
