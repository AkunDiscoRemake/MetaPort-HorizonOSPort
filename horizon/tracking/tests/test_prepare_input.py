# SPDX-License-Identifier: GPL-3.0-only
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from horizon.tracking.prepare_input import prepare


class FocusedInputPreparationTests(unittest.TestCase):
    def test_unverified_image_is_rejected_before_extraction(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);(root/'odm.img').write_bytes(b'fixture')
            report=root/'reconstruction.json'
            report.write_text(json.dumps({'partitions':{'odm':{'sha256_match':False,'sha256':'0'*64}}}))
            with patch('horizon.tracking.prepare_input.dump_entry') as dump:
                with self.assertRaisesRegex(ValueError,'ODM verification'):prepare(root,report,root/'out')
                dump.assert_not_called()

    def test_wrong_engine_cannot_use_pinned_addresses(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);raw=b'fixture';(root/'odm.img').write_bytes(raw)
            report=root/'reconstruction.json'
            report.write_text(json.dumps({'partitions':{'odm':{'sha256_match':True,'sha256':hashlib.sha256(raw).hexdigest()}}}))
            with patch('horizon.tracking.prepare_input.dump_entry',side_effect=lambda image,entry,path:path.write_bytes(b'wrong ELF')):
                with self.assertRaisesRegex(ValueError,'Wrong tracking engine'):prepare(root,report,root/'out')
            self.assertFalse((root/'out/input-strings.json').exists())

class VisualStringTargetsTests(unittest.TestCase):
    def test_exact_fields_complete_strings_and_elf_addresses(self):
        from horizon.tracking.prepare_input import visual_string_targets
        data=b'\0SkinningWeights\0NotSkinningWeights\0PreRotation\0'
        sections=f'[ 1] .rodata PROGBITS 00002000 00000000 {len(data):08x}'
        targets=visual_string_targets(data,sections)
        self.assertEqual([x['text'] for x in targets],['SkinningWeights','PreRotation'])
        self.assertEqual(targets[0]['address'],0x2001)
        with self.assertRaises(ValueError):visual_string_targets(data,sections.replace('00000000','00000100'))
