# SPDX-License-Identifier: GPL-3.0-only
import copy
import unittest
from horizon.ui.focus_wire_contract import load,verify

class FocusWireContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.java,cls.native=load()
    def test_original_java_and_native_contracts_agree(self):
        result=verify(self.java,self.native)
        self.assertEqual([r['transaction'] for r in result['transactions']],list(range(1,12)))
        self.assertEqual(result['parcel_fields']['ImmersiveApp'],['packageName','pid','uid','isTopActivity'])
        self.assertFalse(result['original_proxy_executed'])
        self.assertFalse(result['service_published'])
    def test_changed_native_decoder_rejected(self):
        native=copy.deepcopy(self.native)
        for f in native['functions']:
            if f['elf_address']==0xaa00:f['c']+=' altered'
        with self.assertRaises(ValueError):verify(self.java,native)
    def test_missing_java_contracts_rejected(self):
        with self.assertRaises(ValueError):verify({'framework_dex_additions':[]},self.native)
    def test_changed_java_writer_rejected(self):
        java=copy.deepcopy(self.java)
        for addition in java['framework_dex_additions']:
            for member in addition.get('members',[]):
                for item in member.get('startup_contracts',[]):
                    if item['class_file']=='oculus/internal/ImmersiveApp.smali':
                        item['original_smali']=item['original_smali'].replace('->pid:I','->uid:I')
        with self.assertRaises(ValueError):verify(java,self.native)
