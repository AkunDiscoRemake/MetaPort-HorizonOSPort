# SPDX-License-Identifier: GPL-3.0-only
import hashlib
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from tools.disassemble_original_arm64 import disassemble_verified

class PinnedDisassembly(unittest.TestCase):
    def test_rejects_wrong_size_hash_and_format_before_launching_tools(self):
        with tempfile.TemporaryDirectory() as d, patch('tools.disassemble_original_arm64.subprocess.Popen') as launch:
            p=Path(d)/'original';p.write_bytes(b'not an ELF')
            for size,digest in ((1,'bad'),(10,'bad'),(10,hashlib.sha256(p.read_bytes()).hexdigest())):
                with self.assertRaises(ValueError):disassemble_verified(p,Path(d)/'out.gz',digest,size)
            launch.assert_not_called()
