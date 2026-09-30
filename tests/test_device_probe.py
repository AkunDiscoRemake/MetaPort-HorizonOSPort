import subprocess
import unittest
from unittest.mock import patch
from tools.device_probe import collect, PROPERTIES


class ProbeTests(unittest.TestCase):
    @patch("tools.device_probe.subprocess.run")
    def test_only_read_queries_and_filtered_report(self, run):
        run.side_effect = [subprocess.CompletedProcess([], 0, "value\n", "")
                           for _ in PROPERTIES] + [subprocess.CompletedProcess([], 0,
                           "feature:android.hardware.vulkan.version=1\n"
                           "feature:unrelated.feature\n", "")]
        result = collect("private-serial")
        self.assertEqual(result["declared_features"], ["android.hardware.vulkan.version=1"])
        self.assertNotIn("private-serial", str(result))
        self.assertEqual(result["arcore_runtime_availability"], "NOT_TESTED")
        for call in run.call_args_list:
            command = call.args[0]
            self.assertEqual(command[:4], ["adb", "-s", "private-serial", "shell"])
            self.assertIn(command[4], ("getprop", "pm"))

    @patch("tools.device_probe.subprocess.run")
    def test_failure_is_not_success(self, run):
        run.return_value = subprocess.CompletedProcess([], 1, "", "private details")
        with self.assertRaisesRegex(RuntimeError, "ADB query failed"):
            collect()
