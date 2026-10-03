import unittest
from guest.dtb import relocate_virtio


class DtbTests(unittest.TestCase):
    def test_single_controller_relocated_other_nodes_unchanged(self):
        node='\tvirtio_mmio@a000000 {\n\t\treg = <0x0 0xa000000 0x0 0x200>;\n\t};'
        raw='/dts-v1/;\n/ {\n\tcompatible = "linux,dummy-virt";\n'+node+'\n\tuart {\n\t};\n};'
        result=relocate_virtio(raw)
        self.assertIn('compatible = "simple-bus"',result)
        self.assertIn('compatible = "metaport,virt", "linux,dummy-virt"',result)
        self.assertEqual(result.count('metaport,boot-controller-alias;'),1)
        self.assertIn('\t\tvirtio_mmio@a000000',result)
        self.assertIn('\tuart {\n\t};',result)
        self.assertEqual(result.count('reg = <0x0 0xa000000 0x0 0x200>'),1)

    def test_reject_ambiguous_or_missing_bus(self):
        with self.assertRaises(ValueError):relocate_virtio('/ {};')
        with self.assertRaises(ValueError):relocate_virtio('\tsoc {\n\t};')
