# SPDX-License-Identifier: GPL-3.0-only
import hashlib
from pathlib import Path
import struct
import tempfile
import unittest
from guest.trace_bootconfig import append_trace_config, CONFIG, MAGIC, MAX_INITRD


class TraceBootconfigTests(unittest.TestCase):
    def test_original_bytes_preserved_and_footer_valid_for_all_alignments(self):
        with tempfile.TemporaryDirectory() as folder:
            source, output = Path(folder)/'original', Path(folder)/'diagnostic'
            for alignment in range(4):
                raw = b'fixture-cpio-bytes' + b'x'*alignment
                source.write_bytes(raw)
                report = append_trace_config(source, output)
                blob = output.read_bytes()
                self.assertEqual(source.read_bytes(), raw)
                self.assertEqual(blob[:len(raw)], raw)
                self.assertEqual(len(blob) % 4, 0)
                self.assertTrue(blob.endswith(MAGIC))
                size, checksum = struct.unpack('<II', blob[-20:-12])
                config = blob[-20-size:-20]
                self.assertEqual(len(raw)+size+20, len(blob))
                self.assertEqual(config.rstrip(b'\0'), CONFIG)
                self.assertEqual(sum(config), checksum)
                self.assertEqual(report['original_initrd_sha256'], hashlib.sha256(raw).hexdigest())
                self.assertFalse(report['vendor_bootconfig_applied'])

    def test_no_original_or_link_overwrite(self):
        with tempfile.TemporaryDirectory() as folder:
            source, link = Path(folder)/'original', Path(folder)/'link'
            source.write_bytes(b'fixture')
            with self.assertRaises(ValueError): append_trace_config(source, source)
            link.symlink_to(source)
            with self.assertRaises(ValueError): append_trace_config(source, link)
            link.unlink(); link.hardlink_to(source)
            with self.assertRaises(ValueError): append_trace_config(source, link)
            self.assertEqual(source.read_bytes(), b'fixture')

    def test_reject_existing_config_empty_and_oversize_input(self):
        with tempfile.TemporaryDirectory() as folder:
            source, output = Path(folder)/'original', Path(folder)/'diagnostic'
            for raw in (b'', b'fixture'+MAGIC):
                source.write_bytes(raw)
                with self.assertRaises(ValueError): append_trace_config(source, output)
            with source.open('wb') as stream: stream.truncate(MAX_INITRD+1)
            with self.assertRaises(ValueError): append_trace_config(source, output)
            self.assertFalse(output.exists())

    def test_only_separate_instance_and_metadata_events(self):
        self.assertTrue(CONFIG.startswith(b'ftrace.instance.metaport_signals {'))
        self.assertIn(b'"signal:signal_generate", "sched:sched_process_exit"', CONFIG)
        self.assertNotIn(b'signal_deliver', CONFIG)
        self.assertNotIn(b'kernel.', CONFIG)
        self.assertNotIn(b'init.', CONFIG)
        self.assertEqual(CONFIG.count(b'events ='), 1)
