import struct
import unittest
from horizon.ui.prepare_shell import TARGETS, select_symbols, executable_ranges

class ShellPreparationTests(unittest.TestCase):
    def symbols(self):
        return '\n'.join(f'{i+1}: {0x1000+i*16:016x} 16 FUNC GLOBAL DEFAULT 9 {name}' for i,name in enumerate(TARGETS))
    def test_fixed_exports_preserve_priority(self):
        rows=select_symbols(self.symbols())
        self.assertEqual([r['symbol'] for r in rows],TARGETS)
        self.assertEqual(rows[0]['elf_address'],0x1000)
    def test_missing_import_and_duplicate_fail_closed(self):
        for text in (self.symbols().replace('GLOBAL DEFAULT 9','GLOBAL DEFAULT UND',1),
                     self.symbols()+'\n'+self.symbols().splitlines()[0], ''):
            with self.assertRaises(ValueError):select_symbols(text)
    def elf(self):
        b=bytearray(256);b[:6]=b'\x7fELF\x02\x01'
        struct.pack_into('<HH',b,16,3,183);struct.pack_into('<Q',b,32,64)
        struct.pack_into('<HH',b,54,56,1)
        struct.pack_into('<IIQQQQQQ',b,64,1,5,128,0x1000,0x1000,128,256,4096)
        return b
    def test_uses_file_backed_executable_extent_not_bss(self):
        self.assertEqual(executable_ranges(self.elf()),[(0x1000,0x1080)])
    def test_bad_machine_and_extent_rejected(self):
        b=self.elf();struct.pack_into('<H',b,18,62)
        with self.assertRaises(ValueError):executable_ranges(b)
        b=self.elf();struct.pack_into('<Q',b,64+32,1000)
        with self.assertRaises(ValueError):executable_ranges(b)
