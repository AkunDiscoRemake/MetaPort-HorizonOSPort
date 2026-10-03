"""Reproduce cross-width vtable reuse with a real public FlatBuffers writer."""
import importlib.util
import json
import os
from pathlib import Path
import struct
import subprocess
import tempfile
import unittest
from handtracking.ai.pte_schema import describe


def fixture():
    import flatbuffers
    b=flatbuffers.Builder(256)
    # This unused narrow table seeds a (field-offset=4) vtable of object size 8.
    b.StartObject(1);b.PrependInt32Slot(0,7,0);b.EndObject()
    b.StartObject(1);b.PrependInt64Slot(0,384,0);wide=b.EndObject()
    b.StartObject(2);b.PrependUOffsetTRelativeSlot(1,wide,0);b.PrependUint8Slot(0,2,0);value=b.EndObject()
    b.StartVector(4,1,4);b.PrependUOffsetTRelative(value);values=b.EndVector()
    b.StartVector(4,1,4);b.PrependInt32(0);outputs=b.EndVector()
    name=b.CreateString('hidden_dim')
    b.StartObject(9);b.PrependUOffsetTRelativeSlot(0,name,0);b.PrependUOffsetTRelativeSlot(2,values,0)
    b.PrependUOffsetTRelativeSlot(4,outputs,0);plan=b.EndObject()
    b.StartVector(4,1,4);b.PrependUOffsetTRelative(plan);plans=b.EndVector()
    b.StartObject(8);b.PrependUint32Slot(0,1,0);b.PrependUOffsetTRelativeSlot(1,plans,0);root=b.EndObject()
    b.Finish(root,file_identifier=b'ET12');raw=bytes(b.Output())
    # Add the documented 24-byte extended header. Relative table offsets stay
    # unchanged; moving the body by 24 also preserves its 8-byte alignment.
    result=bytearray(struct.pack('<I',struct.unpack_from('<I',raw)[0]+24)+b'ET12'+
        b'eh00'+struct.pack('<IQQ',24,len(raw)+24,0)+raw[8:])
    return result


@unittest.skipUnless(importlib.util.find_spec('flatbuffers'),'optional public FlatBuffers writer')
class ReferenceFixtureTests(unittest.TestCase):
    def test_public_writer_reproduces_strict_reader_extent_warning(self):
        raw=fixture();root=struct.unpack_from('<I',raw)[0]
        value=describe(raw,root)['execution_plans'][0]['outputs'][0]
        self.assertEqual(value['kind'],'SCALAR_LAYOUT_UNRESOLVED')
        self.assertEqual(value['layout_evidence']['vtable_prefix_hex'],'060008000400')
        self.assertEqual(value['layout_evidence']['expected_scalar_bytes'],8)
        self.assertNotIn('serialized_value',value)

    @unittest.skipUnless(os.environ.get('METAPORT_REFERENCE_PROBE'),'native public-schema probe is CI-built')
    def test_native_verifier_accepts_reuse_and_rejects_bad_bounds(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'synthetic.pte';raw=fixture();path.write_bytes(raw)
            def run():
                return subprocess.run([os.environ['METAPORT_REFERENCE_PROBE'],str(path)],
                    capture_output=True,text=True,timeout=20)
            result=run();self.assertEqual(result.returncode,0,result.stderr)
            metadata=json.loads(result.stdout)
            self.assertTrue(metadata['public_schema_verifier_passed'])
            self.assertEqual(metadata['int_getters'],{'hidden_dim':384})
            self.assertFalse(metadata['model_executed'])
            damaged=bytearray(raw);struct.pack_into('<I',damaged,0,len(raw)+64);path.write_bytes(damaged)
            result=run();self.assertEqual(result.returncode,0)
            self.assertFalse(json.loads(result.stdout)['public_schema_verifier_passed'])
            damaged=bytearray(raw);struct.pack_into('<Q',damaged,16,1<<40);path.write_bytes(damaged)
            self.assertNotEqual(run().returncode,0)
            path.write_bytes(raw[:63]);self.assertNotEqual(run().returncode,0)
