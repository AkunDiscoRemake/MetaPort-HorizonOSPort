# SPDX-License-Identifier: GPL-3.0-only
import hashlib
import struct
import tempfile
import unittest
import zipfile
from pathlib import Path
from horizon.ui.framework_dex import additions,REQUIRED,definitions
from horizon.ui.tests.test_dex_contract import seal


def class_dex(name):
    # Metadata-only test fixture, not runnable code or a substitute framework.
    b=bytearray(152);b[:8]=b'dex\n039\0'
    struct.pack_into('<II',b,36,112,0x12345678)
    for at,offset in ((56,112),(64,116),(96,120)):struct.pack_into('<II',b,at,1,offset)
    struct.pack_into('<I',b,112,152)
    b.extend(bytes([len(name)])+name.encode()+b'\0')
    struct.pack_into('<I',b,32,len(b));return seal(b)


class FrameworkDexTests(unittest.TestCase):
    def test_original_bytes_and_new_index_are_preserved(self):
        with tempfile.TemporaryDirectory() as d:
            apk=Path(d)/'a.apk';jar=Path(d)/'f.jar';data=class_dex(REQUIRED)
            with zipfile.ZipFile(apk,'w') as z:z.writestr('classes2.dex',class_dex('Lapp/Own;'))
            with zipfile.ZipFile(jar,'w') as z:z.writestr('classes.dex',data)
            members,evidence=additions(apk,jar)
            self.assertEqual(members,{'classes3.dex':data})
            self.assertEqual(evidence['members'][0]['sha256'],hashlib.sha256(data).hexdigest())
            self.assertFalse(evidence['framework_services_ported'])

    def test_collisions_missing_definition_and_boot_namespaces_fail_closed(self):
        for extra in ('Lapp/Own;','Landroid/os/Anything;','Lother/Thing;'):
            with self.subTest(extra=extra),tempfile.TemporaryDirectory() as d:
                apk=Path(d)/'a.apk';jar=Path(d)/'f.jar'
                with zipfile.ZipFile(apk,'w') as z:z.writestr('classes.dex',class_dex('Lapp/Own;'))
                with zipfile.ZipFile(jar,'w') as z:z.writestr('classes.dex',class_dex(extra))
                with self.assertRaises(ValueError):additions(apk,jar)

    def test_bad_dex_checksum_rejected(self):
        data=bytearray(class_dex(REQUIRED));data[-1]^=1
        with self.assertRaises(ValueError):definitions(bytes(data))
