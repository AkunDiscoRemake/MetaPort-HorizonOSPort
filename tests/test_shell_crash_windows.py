# SPDX-License-Identifier: GPL-3.0-only
import hashlib
from pathlib import Path
import struct
import tempfile
import unittest
from unittest.mock import patch
from tools.shell_crash_windows import instruction_window,collect

class CrashInstructions(unittest.TestCase):
    def image(self):
        blob=bytearray(320);blob[:6]=b'\x7fELF\x02\x01'
        struct.pack_into('<H',blob,18,183);struct.pack_into('<Q',blob,32,64)
        struct.pack_into('<HH',blob,54,56,1)
        struct.pack_into('<II6Q',blob,64,1,5,256,4096,4096,64,64,4096)
        blob[256:]=bytes.fromhex('1f2003d5')*16
        return bytes(blob)

    def test_pc_bounds_and_bytes(self):
        data=self.image();row=instruction_window(data,4096)
        self.assertEqual(row['bytes_hex'],'1f2003d5'*12)
        self.assertEqual(row['start_elf'],4096)
        for pc in (0,4097,4160):
            with self.assertRaises(ValueError):instruction_window(data,pc)

    def test_only_verified_packaged_frames(self):
        data=self.image();sha=hashlib.sha256(data).hexdigest()
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'libc++.so';path.write_bytes(data)
            bundle={'nodes':[{'soname':'libc++.so','sha256':sha}]}
            text='#00 pc 0000000000001000 /data/app/example/lib/arm64/libc++.so (function+0)\n'
            with patch('tools.shell_crash_windows.command',return_value=('nop','')) as command:
                result=collect(text*20,d,bundle)
                self.assertEqual(len(result['frames']),1);command.assert_called_once()
                self.assertFalse(result['crash_cause_proven'])
                path.write_bytes(data+b'altered')
                with self.assertRaises(ValueError):collect(text,d,bundle)
