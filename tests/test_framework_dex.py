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

    def test_second_framework_preserves_prior_dex_and_rejects_collisions(self):
        with tempfile.TemporaryDirectory() as d:
            apk=Path(d)/'a.apk';jar=Path(d)/'f.jar'
            platform='Lcom/oculus/os/ActivityManagerUtils;'
            prior={'classes2.dex':class_dex(REQUIRED)}
            with zipfile.ZipFile(apk,'w') as z:z.writestr('classes.dex',class_dex('Lapp/Own;'))
            with zipfile.ZipFile(jar,'w') as z:z.writestr('classes.dex',class_dex(platform))
            members,evidence=additions(apk,jar,prior_members=prior,
                                      source_path='/framework/platform.jar',required=platform)
            self.assertEqual(set(members),{'classes3.dex'})
            self.assertEqual(definitions(members['classes3.dex']),{platform})
            self.assertEqual(evidence['required_definition'],platform)
            self.assertEqual(evidence['source_path'],'/framework/platform.jar')
            self.assertEqual(prior,{'classes2.dex':class_dex(REQUIRED)})
            for bad in ({'classes2.dex':class_dex(platform)},
                        {'classes.dex':class_dex(REQUIRED)},
                        {'classes2.dex':class_dex('Lapp/Own;')},
                        {'classes128.dex':class_dex(REQUIRED)}):
                with self.subTest(prior=tuple(bad)),self.assertRaises(ValueError):
                    additions(apk,jar,prior_members=bad,required=platform)

    def test_bad_dex_checksum_rejected(self):
        data=bytearray(class_dex(REQUIRED));data[-1]^=1
        with self.assertRaises(ValueError):definitions(bytes(data))

    def test_header_normalization_does_not_change_code_or_data(self):
        from horizon.ui.framework_dex import normalized_framework_header
        original=bytearray(class_dex(REQUIRED));original[8:32]=bytes(24);original=bytes(original)
        result,evidence=normalized_framework_header(original)
        self.assertEqual(result[:8]+result[32:],original[:8]+original[32:])
        self.assertEqual(definitions(result),{REQUIRED})
        self.assertTrue(evidence['header_checksums_recomputed'])
        self.assertEqual(evidence['source_dex_sha256'],hashlib.sha256(original).hexdigest())
        _,again=normalized_framework_header(result)
        self.assertFalse(again['header_checksums_recomputed'])

    def test_original_apk_checksum_validation_is_not_relaxed(self):
        with tempfile.TemporaryDirectory() as d:
            apk=Path(d)/'a.apk';jar=Path(d)/'f.jar'
            corrupt=bytearray(class_dex('Lapp/Own;'));corrupt[8:32]=bytes(24)
            with zipfile.ZipFile(apk,'w') as z:z.writestr('classes.dex',corrupt)
            with zipfile.ZipFile(jar,'w') as z:z.writestr('classes.dex',class_dex(REQUIRED))
            with self.assertRaisesRegex(ValueError,'checksum'):additions(apk,jar)

    def test_meta_registry_extension_does_not_allow_host_registry_replacement(self):
        from horizon.ui.framework_dex import forbidden_boot_definition
        self.assertTrue(forbidden_boot_definition('Landroid/app/VrosSystemServiceRegistry;'))
        self.assertTrue(forbidden_boot_definition('Landroid/app/VrosSystemServiceRegistry$10;'))
        self.assertTrue(forbidden_boot_definition('Landroid/app/SystemServiceRegistry;'))
        self.assertTrue(forbidden_boot_definition('Landroid/app/ContextImpl;'))
        self.assertTrue(forbidden_boot_definition('Landroid/app/VrosSystemServiceRegistryOther;'))

    def test_canonical_inventory_detects_changed_disassembly(self):
        from horizon.ui.select_framework_classes import smali_inventory
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);path=root/'Vector4f.smali';path.write_text('.method original\nreturn-void\n')
            before=smali_inventory(root)
            path.write_text('.method changed\nreturn-void\n')
            self.assertNotEqual(before,smali_inventory(root))
            path.unlink()
            with self.assertRaises(ValueError):smali_inventory(root)

    def test_comparison_reports_change_without_accepting_it(self):
        from horizon.ui.select_framework_classes import compare_smali
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);a=root/'before';b=root/'after';a.mkdir();b.mkdir()
            (a/'A.smali').write_text('.method original\nreturn-void\n')
            (b/'A.smali').write_text('.method changed\nreturn-void\n')
            with self.assertRaisesRegex(ValueError,'first_changed') as error:compare_smali(a,b,1)
            self.assertIn('original',str(error.exception));self.assertIn('changed',str(error.exception))
            (b/'A.smali').write_bytes((a/'A.smali').read_bytes())
            self.assertEqual(len(compare_smali(a,b,1)),1)
            with self.assertRaisesRegex(ValueError,'expected'):compare_smali(a,b,2)

    def test_loader_diagnostics_do_not_filter_out_installer_uid(self):
        from tools.probe_original_shell import loader_diagnostics
        commands=[]
        result=loader_diagnostics(lambda args:commands.append(args) or {'exit_code':0,'text':'loader evidence'})
        self.assertEqual(result['text'],'loader evidence')
        self.assertIn('-d',commands[0]);self.assertIn('1200',commands[0])
        self.assertFalse(any(a.startswith('--uid') for a in commands[0]))
        self.assertTrue(any(a.startswith('--regex=') for a in commands[0]))

    def test_recovered_contract_is_bounded_and_matches_canonical_hash(self):
        from horizon.ui.select_framework_classes import startup_contracts, STARTUP_CONTRACTS
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);name=STARTUP_CONTRACTS[0];path=root/name
            path.parent.mkdir(parents=True);path.write_text('original service boundary')
            inventory={name:hashlib.sha256(path.read_bytes()).hexdigest()}
            rows=startup_contracts(root,inventory)
            self.assertEqual(rows[0]['original_smali'],'original service boundary')
            self.assertEqual(startup_contracts(root,{}),[])
            path.write_text('changed')
            with self.assertRaisesRegex(ValueError,'Changed'):startup_contracts(root,inventory)
            path.write_bytes(b'x'*(96*1024+1))
            with self.assertRaisesRegex(ValueError,'budget'):startup_contracts(root,inventory)
