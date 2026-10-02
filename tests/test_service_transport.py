# SPDX-License-Identifier: GPL-3.0-only
import hashlib
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from horizon.ui.service_transport import OWNERS,TYPES,verify_transport

class ServiceTransportTests(unittest.TestCase):
    def fixture(self,root):
        a=root/'before';b=root/'after';hashes={}
        for name in (*OWNERS,'untouched/Original.smali'):
            text='.class Loriginal;\n'+('\n'.join(TYPES) if name in OWNERS else 'return-void')+'\n'
            path=a/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_text(text)
            hashes[name]=hashlib.sha256(path.read_bytes()).hexdigest()
            if name in OWNERS:
                for old,new in TYPES.items():text=text.replace(old,new)
            path=b/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_text(text)
        return a,b,hashes
    def test_only_declared_descriptors_can_change(self):
        with tempfile.TemporaryDirectory() as d:
            a,b,hashes=self.fixture(Path(d))
            with patch('horizon.ui.service_transport.CONTRACT_HASHES',hashes):
                self.assertEqual(set(verify_transport(a,b)),set(OWNERS))
                path=b/OWNERS[0];path.write_text(path.read_text()+'return-void\n')
                with self.assertRaisesRegex(ValueError,'instructions'):verify_transport(a,b)
    def test_other_class_and_source_identity_are_protected(self):
        with tempfile.TemporaryDirectory() as d:
            a,b,hashes=self.fixture(Path(d))
            with patch('horizon.ui.service_transport.CONTRACT_HASHES',{}):
                with self.assertRaisesRegex(ValueError,'Unrecognized'):verify_transport(a,b)
            with patch('horizon.ui.service_transport.CONTRACT_HASHES',hashes):
                (b/'untouched/Original.smali').write_text('changed')
                with self.assertRaisesRegex(ValueError,'Unexpected transport change'):verify_transport(a,b)
                (b/'untouched/Original.smali').unlink()
                with self.assertRaisesRegex(ValueError,'inventory'):verify_transport(a,b)

    def test_anr_is_attributed_to_exact_package(self):
        from tools.probe_original_shell import contains_application_anr
        self.assertTrue(contains_application_anr('E ActivityManager: ANR in com.oculus.vrshell\nReason: startup'))
        self.assertFalse(contains_application_anr('ANR in com.oculus.vrshell.other'))
        self.assertFalse(contains_application_anr('ANR in org.metaport.port.test'))
        self.assertFalse(contains_application_anr('Status: ok'))

    def test_focus_source_selection_is_bounded_and_not_all_server_classes(self):
        from horizon.ui.focus_contracts import focus_names
        self.assertEqual(focus_names({'Lother/Server;','Loriginal/VrFocusService;'}),['Loriginal/VrFocusService;'])
        with self.assertRaises(ValueError):focus_names({f'Loriginal/VrFocusService${i};' for i in range(65)})

    def test_native_recovery_never_executes_or_packages_daemon(self):
        from horizon.ui.focus_contracts import native_contracts
        paths=('/bin/vrfocusserver','/etc/init/vrfocusserver.rc','/lib64/libvrfocus_interface-cpp.so')
        inventory={'system_ext':{'entries':[{'path':p,'kind':'file','size_bytes':4} for p in paths]}}
        reconstruction={'partitions':{'system_ext':{'sha256':'verified-image-evidence'}}}
        commands=[]
        with tempfile.TemporaryDirectory() as d:
            with patch('horizon.ui.focus_contracts.dump_entry',side_effect=lambda image,entry,target:target.write_bytes(b'test')):
                with patch('horizon.ui.focus_contracts.command',side_effect=lambda args,**kw:(commands.append(args) or 'analysis','')):
                    rows=native_contracts(Path(d),inventory,reconstruction,Path(d))
        self.assertEqual(len(rows),3)
        self.assertTrue(all(not r['executed'] and not r['packaged_in_apk'] for r in rows))
        self.assertEqual({c[0] for c in commands},{'readelf','aarch64-linux-gnu-objdump'})
        self.assertEqual(rows[1]['original_init'],'test')
