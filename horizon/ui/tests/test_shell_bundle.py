# SPDX-License-Identifier: GPL-3.0-only
import hashlib
from pathlib import Path
import tempfile
import unittest
import zipfile
from horizon.ui.bundle_shell_dependencies import candidate,compare_apks,signatures

class OriginalBundle(unittest.TestCase):
    def test_system_precedence_is_explicit_not_vendor_guess(self):
        inv={k:{'entries':[]} for k in ('system','system_ext','vendor')}
        for part,path in (('system','/system/lib64/libx.so'),('vendor','/lib64/libx.so')):
            inv[part]['entries'].append({'kind':'file','path':path})
        self.assertEqual(candidate(inv,'libx.so')[0],'system')
        self.assertIsNone(candidate(inv,'libmissing.so'))
        inv['system']['entries']*=2
        with self.assertRaises(ValueError):candidate(inv,'libx.so')

    def test_only_signature_metadata_removed(self):
        self.assertTrue(signatures('META-INF/CERT.RSA'))
        self.assertTrue(signatures('META-INF/MANIFEST.MF'))
        self.assertFalse(signatures('META-INF/LICENSE'))
        self.assertFalse(signatures('classes.dex'))

    def test_original_members_and_added_hashes(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);original=root/'original.apk';target=root/'target.apk'
            with zipfile.ZipFile(original,'w') as z:
                z.writestr('classes.dex',b'original');z.writestr('META-INF/CERT.RSA',b'old signature')
            def build(code=b'original',extra=False):
                with zipfile.ZipFile(target,'w') as z:
                    z.writestr('classes.dex',code);z.writestr('lib/arm64-v8a/libx.so',b'library')
                    z.writestr('META-INF/TEST.RSA',b'test signature')
                    if extra:z.writestr('assets/unapproved',b'extra')
            added={'lib/arm64-v8a/libx.so':hashlib.sha256(b'library').hexdigest()}
            build();compare_apks(original,target,added)
            build(b'patched')
            with self.assertRaises(ValueError):compare_apks(original,target,added)
            build(extra=True)
            with self.assertRaises(ValueError):compare_apks(original,target,added)
            build()
            with self.assertRaises(ValueError):compare_apks(original,target,{'lib/arm64-v8a/libx.so':'bad'})
