# SPDX-License-Identifier: GPL-3.0-only
import hashlib
import json
import unittest
from unittest.mock import patch
from horizon.ui import prepare_shell_threads as threads

class ThreadSelectionTests(unittest.TestCase):
    def test_prior_analysis_contains_all_candidate_references(self):
        evidence=json.loads(threads.EVIDENCE.read_text())
        base=int(evidence['image_base'],16)
        for address,caller,_ in threads.TARGETS:
            matches=[f for f in evidence['functions'] if f['elf_address']==caller]
            self.assertEqual(len(matches),1)
            self.assertIn(f'FUN_{address+base:08x}',matches[0]['c_like'])

    def test_rejects_unpinned_binary(self):
        with self.assertRaisesRegex(ValueError,'Unpinned library'):
            threads.select(b'not the original',{})

    def test_selection_and_bounds(self):
        blob=b'test fixture only'
        sha=hashlib.sha256(blob).hexdigest()
        evidence=json.loads(threads.EVIDENCE.read_text())
        evidence['program_sha256']=sha
        with patch.object(threads,'POLICY') as policy, patch.object(threads,'executable_ranges') as ranges:
            policy.read_text.return_value=json.dumps({'library_sha256':sha})
            ranges.return_value=[(0,0x2000000)]
            self.assertEqual(len(threads.select(blob,evidence)),5)
            ranges.return_value=[]
            with self.assertRaisesRegex(ValueError,'outside executable'):
                threads.select(blob,evidence)
            ranges.return_value=[(0,0x2000000)]
            evidence['functions']=[]
            with self.assertRaisesRegex(ValueError,'Missing prior reference'):
                threads.select(blob,evidence)
