import unittest
from horizon.ui.loader_audit import audit

class LoaderAuditTests(unittest.TestCase):
    def apk(self, needs):
        return {'sha256':'test','native_libraries':[{'apk_member':'lib/arm64-v8a/libshell.so','needed':needs}]}
    def test_platform_private_library_is_not_public_api(self):
        inv={'system':{'entries':[{'kind':'file','path':'/system/lib64/libcutils.so'}]}}
        r=audit(self.apk(['libcutils.so','libandroid.so']),inv)
        self.assertEqual(r['unresolved_for_unprivileged_apk'],['libcutils.so'])
        self.assertFalse(r['port_ready']);self.assertFalse(r['runtime_load_tested'])
    def test_cycles_are_finite_and_missing_edges_remain_blockers(self):
        a=self.apk(['libother.so']);a['native_libraries'].append({'apk_member':'lib/arm64-v8a/libother.so','needed':['libshell.so','libmissing.so']})
        r=audit(a,{})
        self.assertEqual(len(r['nodes']),3)
        self.assertEqual(r['unresolved_for_unprivileged_apk'],['libmissing.so'])
    def test_32bit_inventory_does_not_resolve_arm64(self):
        inv={'system':{'entries':[{'kind':'file','path':'/system/lib/libprivate.so'}]}}
        r=audit(self.apk(['libprivate.so']),inv)
        self.assertEqual(r['nodes'][1]['classification'],'NOT_LOCATED_IN_CAPTURED_INVENTORY')
    def test_missing_metadata_not_empty_dependency_list(self):
        a=self.apk([]);del a['native_libraries'][0]['needed']
        self.assertEqual(audit(a,{})['unresolved_for_unprivileged_apk'],['libshell.so'])
