# SPDX-License-Identifier: GPL-3.0-only
import hashlib
import unittest
from tools.prepare_dex_tools import patch_writer,WRITER_ANCHOR

class DexWriterPatchTests(unittest.TestCase):
    def test_only_ordering_line_is_inserted(self):
        raw=('before\n'+WRITER_ANCHOR+'\nafter\n').encode()
        result=patch_writer(raw,hashlib.sha256(raw).hexdigest()).decode()
        self.assertTrue(result.startswith('before\n'));self.assertTrue(result.endswith(WRITER_ANCHOR+'\nafter\n'))
        self.assertEqual(result.count('classEntries.sort'),1)
        self.assertIn('entry -> entry.getValue()',result)

    def test_source_identity_and_unique_anchor_are_required(self):
        raw=WRITER_ANCHOR.encode()
        with self.assertRaisesRegex(ValueError,'pinned'):patch_writer(raw)
        for raw in (b'no anchor',(WRITER_ANCHOR*2).encode()):
            with self.assertRaisesRegex(ValueError,'anchor'):patch_writer(raw,hashlib.sha256(raw).hexdigest())
