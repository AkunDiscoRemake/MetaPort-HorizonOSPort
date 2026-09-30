import unittest
from guest.inspect_services import select


class ServiceInspectionTests(unittest.TestCase):
    def test_missing_or_symlink_not_silently_successful(self):
        with self.assertRaises(ValueError):select([],{'/file'})
        with self.assertRaises(ValueError):select([{'path':'/file','kind':'symlink'}],{'/file'})

    def test_selection_is_exact(self):
        e=[{'path':'/file','kind':'file'},{'path':'/file.other','kind':'file'}]
        self.assertEqual(list(select(e,{'/file'})),['/file'])
