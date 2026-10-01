# SPDX-License-Identifier: GPL-3.0-only
import unittest
from horizon.tracking.task_profile_evidence import select_profiles


class Profiles(unittest.TestCase):
    def test_aggregate_attributes_and_cycles(self):
        r=select_profiles({'AggregateProfiles':[{'Name':'trackingPolicy','Profiles':['compute','trackingPolicy','other-file']}],
                           'Profiles':[{'Name':'compute','Actions':[{'Name':'SetAttribute','Params':{'Name':'Boost','Value':'15'}}]},
                                       {'Name':'unrelated','Actions':[]}],
                           'Attributes':[{'Name':'Boost','Controller':'cpu','File':'uclamp.min'}]})
        self.assertEqual(set(r['definitions']),{'trackingPolicy','compute'})
        self.assertEqual(r['unresolved_profile_names'],['other-file'])
        self.assertEqual(len(r['referenced_attributes']),1)
        self.assertFalse(r['runtime_applied']);self.assertFalse(r['phone_compatible'])

    def test_ambiguous_or_bad_profile_is_rejected(self):
        with self.assertRaises(ValueError):select_profiles({'Profiles':[{'Name':'hand'},{'Name':'hand'}]})
        with self.assertRaises(ValueError):select_profiles({'Profiles':{}})
        with self.assertRaises(ValueError):select_profiles({'AggregateProfiles':[{'Name':'hand','Profiles':[4]}]})

    def test_unresolved_attribute_is_visible(self):
        r=select_profiles({'Profiles':[{'Name':'HandThread','Actions':[{'Name':'SetAttribute','Params':{'Name':'Missing'}}]}]})
        self.assertEqual(r['unresolved_attribute_names'],['Missing'])

    def test_explicit_config_reference_follows_non_tracking_names(self):
        root={'AggregateProfiles':[{'Name':'SoftRealtimePerformance','Profiles':['cpuPolicy']}],
              'Profiles':[{'Name':'cpuPolicy','Actions':[{'Name':'SetAttribute','Params':{'Name':'Min'}}]}],
              'Attributes':[{'Name':'Min','Controller':'cpu','File':'uclamp.min'}]}
        self.assertEqual(select_profiles(root)['definitions'],{})
        r=select_profiles(root,extra_roots=('SoftRealtimePerformance','cross-file'))
        self.assertEqual(set(r['definitions']),{'SoftRealtimePerformance','cpuPolicy'})
        self.assertEqual(r['unresolved_profile_names'],['cross-file'])
        self.assertEqual(r['referenced_attributes'][0]['Name'],'Min')
        with self.assertRaises(ValueError):select_profiles(root,extra_roots='not-a-list')
