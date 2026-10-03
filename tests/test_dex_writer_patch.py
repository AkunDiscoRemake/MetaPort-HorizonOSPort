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
        self.assertIn('offsetWriter.align();\n'+WRITER_ANCHOR,result)

    def test_source_identity_and_unique_anchor_are_required(self):
        raw=WRITER_ANCHOR.encode()
        with self.assertRaisesRegex(ValueError,'pinned'):patch_writer(raw)
        for raw in (b'no anchor',(WRITER_ANCHOR*2).encode()):
            with self.assertRaisesRegex(ValueError,'anchor'):patch_writer(raw,hashlib.sha256(raw).hexdigest())

    def test_explicit_default_initializer_is_not_trimmed(self):
        from tools.prepare_dex_tools import patch_initializers, INITIALIZER_ANCHOR
        raw=('before\n'+INITIALIZER_ANCHOR+'\nafter').encode()
        self.assertEqual(patch_initializers(raw,hashlib.sha256(raw).hexdigest()),
                         b'before\nreturn encodedValue != null;\nafter')
        with self.assertRaisesRegex(ValueError,'pinned'):patch_initializers(raw)
        for raw in (b'no anchor',(INITIALIZER_ANCHOR*2).encode()):
            with self.assertRaisesRegex(ValueError,'anchor'):
                patch_initializers(raw,hashlib.sha256(raw).hexdigest())
