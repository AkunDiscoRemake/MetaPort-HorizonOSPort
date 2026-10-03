# SPDX-License-Identifier: GPL-3.0-only
import json
import unittest
from horizon.ui.generate_jni_contract import descriptor_types, generate, REPORT, OUTPUT

class JniContractTests(unittest.TestCase):
    def test_types_and_arrays(self):
        self.assertEqual(descriptor_types('(JZLjava/lang/String;[I[[F[Ljava/lang/String;)V'),
            ('void',['jlong','jboolean','jstring','jintArray','jobjectArray','jobjectArray']))
        self.assertEqual(descriptor_types('()Ljava/lang/String;'),('jstring',[]))
    def test_rejects_malformed_descriptors(self):
        for text in ['(V)V','([V)V','(I','()Vgarbage','()','(Ljava/lang/String)V','I)V']:
            with self.subTest(text=text),self.assertRaises(ValueError):descriptor_types(text)
    def test_generated_contract_current_and_not_export_stubs(self):
        text=generate(json.loads(REPORT.read_text()))
        self.assertEqual(text,OUTPUT.read_text())
        self.assertNotIn('JNIEXPORT',text)
        self.assertIn('using nativeInit = jlong',text)
        # Export exists in libshell, but no declaration in this DEX class.
        self.assertNotIn('using nativePassthroughRequest',text)
    def test_rejects_duplicate_methods(self):
        r=json.loads(REPORT.read_text());r['native_declarations']*=2
        with self.assertRaises(ValueError):generate(r)
