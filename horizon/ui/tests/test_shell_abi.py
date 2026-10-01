import importlib.util
import struct
import unittest
from horizon.ui.verify_shell_abi import page_address, slot_address, prove_return, read_va

class ArmAddressTests(unittest.TestCase):
    def test_adrp_uses_actual_elf_pc_not_ghidra_rebase(self):
        self.assertEqual(page_address(0xb0000013,0x1000,19),0x2000)
        self.assertEqual(page_address(0xb0000013,0x101000,19),0x102000)
        self.assertEqual(slot_address(0x2000,0xf9400660,19,True),0x2008)
        with self.assertRaises(ValueError):slot_address(0x2000,0xf9000660,19,True)
        with self.assertRaises(ValueError):page_address(0xb0000013,0x1000,8)

@unittest.skipUnless(importlib.util.find_spec('capstone'),'Install horizon/ui/abi-requirements.txt for ARM64 disassembly tests')
class ReturnProofTests(unittest.TestCase):
    def fixture(self):
        b=bytearray(288);b[:6]=b'\x7fELF\x02\x01'
        struct.pack_into('<HH',b,16,3,183);struct.pack_into('<Q',b,32,64)
        struct.pack_into('<HH',b,54,56,2)
        struct.pack_into('<IIQQQQQQ',b,64,1,5,256,0x1000,0,32,32,4096)
        struct.pack_into('<IIQQQQQQ',b,120,1,6,288,0x2000,0,0,128,4096)
        struct.pack_into('<IIIII',b,256,0xb0000013,0xf9400660,0xd65f03c0,0xb0000008,0xf9000500)
        p={'return_page_instruction':0x1000,'return_load_instruction':0x1004,'return_instruction':0x1008,
           'service_setter_page_instruction':0x100c,'service_setter_store_instruction':0x1010}
        return b,p
    def test_return_global_and_setter_agree(self):
        b,p=self.fixture();r=prove_return(b,p)
        self.assertEqual(r['returned_global_elf_va'],0x2008)
        self.assertEqual(r['return_width_bits'],64)
    def test_rejects_wrong_setter_and_nonexecutable_va(self):
        b,p=self.fixture();struct.pack_into('<I',b,272,0xf9000900)
        with self.assertRaises(ValueError):prove_return(b,p)
        with self.assertRaises(ValueError):read_va(b,0x2000,4)
    def test_does_not_accept_arbitrary_return_register_write(self):
        b,p=self.fixture();struct.pack_into('<I',b,264,0xaa0103e0) # mov x0,x1
        struct.pack_into('<I',b,268,0xd65f03c0)
        struct.pack_into('<II',b,272,0xb0000008,0xf9000500)
        p.update(return_instruction=0x100c,service_setter_page_instruction=0x1010,service_setter_store_instruction=0x1014)
        with self.assertRaises(ValueError):prove_return(b,p)
