import unittest
from guest.labels import adapt,ORIGINAL
from guest.diagnostics import configuration


class LabelTests(unittest.TestCase):
    def test_exact_nodes_existing_types_and_original_prefix_preserved(self):
        source=ORIGINAL+'misc u:object_r:misc_block_device:s0\n'+ORIGINAL+'boot_[ab] u:object_r:boot_block_device:s0\n'
        text,rules=adapt(source,[{'name':'misc'},{'name':'boot_a'}])
        self.assertTrue(text.startswith(source))
        self.assertIn('/dev/block/vda1 u:object_r:misc_block_device:s0',text)
        self.assertEqual(rules[1]['partition'],'boot_a')
        self.assertNotIn('allow ',text)
        self.assertNotIn('setenforce',configuration(True))
        self.assertNotIn('start metaport_bootlog',configuration(True))

    def test_unknown_or_conflicting_partition_rejected(self):
        with self.assertRaises(ValueError):adapt('',[{'name':'misc'}])
        source=ORIGINAL+'misc u:object_r:misc_block_device:s0\n'+ORIGINAL+'misc u:object_r:vd_device:s0\n'
        with self.assertRaises(ValueError):adapt(source,[{'name':'misc'}])
