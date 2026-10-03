# SPDX-License-Identifier: GPL-3.0-only
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile
from handtracking.ai.hand_presentation import inspect_apk

class PresentationTests(unittest.TestCase):
    def test_native_contracts_resources_and_offsets_are_only_evidence(self):
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder)/'fixture.apk'
            with zipfile.ZipFile(p,'w') as z:
                z.writestr('assets/left_hand_diffuse.ktx',b'fixture')
                z.writestr('assets/animations/grab.json',b'{}')
                z.writestr('assets/icon.png',b'fixture')
                z.writestr('lib/arm64-v8a/libvrshell.so',b'\x7fELF\0xrLocateHandJointsEXT\0UnhandledException\0')
            r=inspect_apk(p)
            self.assertEqual(r['matching_resource_count'],2)
            self.assertEqual(r['native_contracts'][0]['strings'],[{'file_offset':5,'text':'xrLocateHandJointsEXT'}])
            self.assertFalse(r['candidate_names_prove_usage'])
            self.assertFalse(r['renderer_integrated'])

    def test_content_size_budget_is_explicit(self):
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder)/'fixture.apk'
            with zipfile.ZipFile(p,'w') as z:z.writestr('lib/arm64-v8a/libvrshell.so',b'\x7fELF\0fixture')
            with patch('handtracking.ai.hand_presentation.MAX_TOTAL',4):
                r=inspect_apk(p)
            self.assertEqual(r['native_contracts'][0]['status'],'SIZE_LIMIT_NOT_SCANNED')
            self.assertEqual(r['native_bytes_scanned'],0)

    def test_candidate_member_path_never_extracted(self):
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder)/'fixture.apk'
            with zipfile.ZipFile(p,'w') as z:z.writestr('../hand.bin',b'fixture')
            r=inspect_apk(p)
            self.assertEqual(len(r['candidate_resources']),1)
            self.assertEqual(list(Path(folder).iterdir()),[p])
