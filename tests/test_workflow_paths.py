# SPDX-License-Identifier: GPL-3.0-only
from pathlib import Path
import fnmatch
import unittest
try:
    import yaml
except ImportError:
    yaml=None

@unittest.skipIf(yaml is None,'Install tools/check-requirements.txt')
class WorkflowPathTests(unittest.TestCase):
    def test_path_filtered_workflows_include_their_own_configuration(self):
        root=Path(__file__).resolve().parents[1]
        for path in sorted((root/'.github/workflows').glob('*.yml')):
            data=yaml.load(path.read_text(),Loader=yaml.BaseLoader)
            push=data.get('on',{}).get('push',{}) or {}
            if not isinstance(push,dict) or 'paths' not in push:continue
            relative=path.relative_to(root).as_posix()
            with self.subTest(workflow=relative):
                self.assertTrue(any(not rule.startswith('!') and fnmatch.fnmatchcase(relative,rule)
                                    for rule in push['paths']), 'Workflow cannot trigger on its own update')
