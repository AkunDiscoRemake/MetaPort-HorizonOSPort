# SPDX-License-Identifier: GPL-3.0-only
import gzip
from pathlib import Path
import tempfile
import unittest
from horizon.ui.disassemble_shell import stream_listing

class FullListingTests(unittest.TestCase):
    def test_instructions_and_data_are_distinguished(self):
        lines=[b' 1000: d65f03c0 ret\n',b' 1004: 00000000 .word 0x0\n',b'00001000 <name>:\n']
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'out.gz';r=stream_listing(lines,p)
            self.assertEqual(r['instruction_rows'],1);self.assertEqual(r['directive_rows'],1)
            self.assertEqual(gzip.decompress(p.read_bytes()),b''.join(lines))
    def test_empty_listing_and_budget_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'out.gz'
            with self.assertRaises(ValueError):stream_listing([b'file format elf64-littleaarch64\n'],p)
            with self.assertRaises(ValueError):stream_listing([b' 1000: d65f03c0 ret\n'],p,max_bytes=2)
