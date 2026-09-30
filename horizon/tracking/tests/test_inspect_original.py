import pickle
from pathlib import Path
import tempfile
import unittest
import zipfile
from horizon.tracking.inspect_original import model_metadata, function_candidates, string_targets, input_string_targets


class MetadataTests(unittest.TestCase):
    def test_pickle_is_inspected_not_loaded(self):
        # This opcode stream would raise if unpickled; genops never calls it.
        blob=b'cbuiltins\neval\n(V1/0\ntR.'
        with tempfile.TemporaryDirectory() as root:
            path=Path(root)/'model.ptl'
            with zipfile.ZipFile(path,'w') as z:
                z.writestr('../bytecode.pkl',blob)
            report=model_metadata(path)
            self.assertFalse(report['executed'])
            self.assertIn('builtins eval',report['pickle_metadata'][0]['strings'])
            self.assertFalse((Path(root).parent/'bytecode.pkl').exists())

    def test_unknown_container_is_not_claimed_supported(self):
        with tempfile.TemporaryDirectory() as root:
            path=Path(root)/'model.ptez';path.write_bytes(b'unknown')
            self.assertEqual(model_metadata(path)['format'],'UNKNOWN')

    def test_model_operator_metadata(self):
        with tempfile.TemporaryDirectory() as root:
            path=Path(root)/'model.ptl'
            with zipfile.ZipFile(path,'w') as z:
                z.writestr('model/bytecode.pkl',pickle.dumps(('forward','aten::conv2d'),protocol=2))
            r=model_metadata(path)
            self.assertIn('aten::conv2d',r['pickle_metadata'][0]['strings'])

    def test_candidates_require_real_defined_function_and_limit(self):
        text=('1: 00001000 80 FUNC GLOBAL DEFAULT 12 HandPoseUpdate\n'
              '2: 00002000 80000 FUNC GLOBAL DEFAULT 12 HandTrackingBig\n'
              '3: 00000000 12 FUNC GLOBAL DEFAULT UND HandTrackingImport\n'
              '4: 00003000 12 OBJECT GLOBAL DEFAULT 12 HandPoseData\n')
        self.assertEqual(function_candidates(text),[{'address':4096,'size':80,'symbol':'HandPoseUpdate'}])
        self.assertEqual(function_candidates(text,limit=0),[])

    def test_stripped_library_registry_and_string_virtual_addresses(self):
        text=('1: 00001000 80 FUNC GLOBAL DEFAULT 12 capabilityRegistryCreateV3\n'
              '2: 00002000 80 FUNC GLOBAL DEFAULT 12 logging_isValidHandle\n')
        self.assertEqual(len(function_candidates(text)),1)
        data=b'\0'*32+b'HandTrackingPose\0'
        sections='[11] .rodata PROGBITS 00004000 000020 000010 00 A 0 0 1'
        self.assertEqual(string_targets(data,sections)[0]['address'],0x4000)
        with self.assertRaises(ValueError): string_targets(data[:33],sections)

    def test_input_targets_are_bounded_complete_strings_not_generic_scales(self):
        raw=b'input0_scale\0input{}_zero_point\0use_uint8_input\0input_format\0unrelated_scale\0'
        sections=f'[11] .rodata PROGBITS 00004000 000020 {len(raw):06x} 00 A 0 0 1'
        result=input_string_targets(bytes(32)+raw,sections)
        self.assertEqual({r['text'] for r in result},
                         {'input0_scale','input{}_zero_point','use_uint8_input','input_format'})
        self.assertEqual(next(r['address'] for r in result if r['text']=='input0_scale'),0x4000)
        with self.assertRaises(ValueError):input_string_targets(bytes(32)+raw[:-1],sections)
        raw=(b'input0_scale\0'*200)+b'x'*600+b'input9_scale\0'
        sections=f'[11] .rodata PROGBITS 00004000 000000 {len(raw):06x} 00 A 0 0 1'
        self.assertEqual(len(input_string_targets(raw,sections)),128)
        self.assertNotIn('input9_scale',{r['text'] for r in input_string_targets(raw,sections)})
