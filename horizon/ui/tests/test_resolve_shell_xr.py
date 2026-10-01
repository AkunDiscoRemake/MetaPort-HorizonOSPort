# SPDX-License-Identifier: GPL-3.0-only
import unittest
from handtracking.ai.tests.test_elf_pointer_evidence import fixture
from horizon.ui.resolve_shell_xr import call_arguments,resolve,string_at
from handtracking.ai.elf_pointer_evidence import load_segments

class XrNames(unittest.TestCase):
    def test_nested_arguments(self):
        args,end=call_arguments('f(1,2), &DAT_00101050, (void **)(p+4));',0)
        self.assertEqual(args,['f(1,2)','&DAT_00101050','(void **)(p+4)'])
        with self.assertRaises(ValueError):call_arguments('f(1',0)

    def test_real_bytes_not_assumed_support(self):
        data=fixture();name=b'xrSetAndroidApplicationThreadKHR\0';data[336:336+len(name)]=name
        report={'image_base':'00100000','firmware_executed':False,'functions':[
            {'elf_address':8192,'status':'DECOMPILED_NOT_VALIDATED','c_like':
             '/* xrFake(1); */ log("https://example.test/xrInvented(1)"); xrGetInstanceProcAddr(f(1,2), &DAT_00101050, (void **)(p+4)); xrBeginSession(s,p);'}]}
        r=resolve(data,report)
        self.assertEqual(len(r['call_sites']),2)
        self.assertEqual(r['call_sites'][0]['requested_procedure'],'xrSetAndroidApplicationThreadKHR')
        self.assertFalse(r['extension_support_verified'])
        report['functions'][0]['c_like']='xrGetInstanceProcAddr(s, unknown, &out);'
        self.assertIn('name_resolution',resolve(data,report)['call_sites'][0])

    def test_non_names_code_and_unmapped_rejected(self):
        data=fixture();data[336:340]=b'abc\0';segments=load_segments(data)
        for address in (0x1050,0x2000,0x9999):self.assertIsNone(string_at(data,segments,address))

    def test_string_may_share_an_executable_load_segment(self):
        data=fixture();name=b'xrBeginSession\0';data[768:768+len(name)]=name
        self.assertEqual(string_at(data,load_segments(data),0x2000),'xrBeginSession')
