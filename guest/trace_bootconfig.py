# SPDX-License-Identifier: GPL-3.0-only
"""Append fixed diagnostic bootconfig to a COPY of the original guest initrd.

Uses the pinned Linux 5.10 tools/bootconfig trailer format. Does not edit any cpio
member, guest init action, SELinux policy, encryption setting or original file.
"""
import hashlib
from pathlib import Path
import stat
import struct

MAGIC = b'#BOOTCONFIG\n'
MAX_INITRD = 128 * 1024 * 1024
INSTANCE = 'metaport_signals'
CONFIG = (b'ftrace.instance.metaport_signals {\n'
          b'  events = "signal:signal_generate", "sched:sched_process_exit"\n'
          b'  tracing_on = 1\n'
          b'  buffer_size = 16KB\n'
          b'}\n')


def append_trace_config(source, destination):
    source, destination = Path(source), Path(destination)
    if not stat.S_ISREG(source.lstat().st_mode) or not 0 < source.stat().st_size <= MAX_INITRD:
        raise ValueError('Expected bounded regular original initrd')
    if destination.is_symlink() or source.resolve() == destination.resolve() or (
            destination.exists() and source.samefile(destination)):
        raise ValueError('Diagnostic initrd must not overwrite the source or a link')
    raw = source.read_bytes()
    if raw.endswith(MAGIC):
        raise ValueError('Existing bootconfig: refuse implicit merge or replacement')
    # The official tool includes the NUL and zero alignment padding in size.
    # Padding aligns the entire file, not just the configuration text.
    config = CONFIG + b'\0'
    config += b'\0' * (-(len(raw) + len(config) + 8 + len(MAGIC)) % 4)
    trailer = config + struct.pack('<II', len(config), sum(config)) + MAGIC
    destination.write_bytes(raw + trailer)
    return {'instance': INSTANCE, 'config_text': CONFIG.decode('ascii'),
            'config_sha256': hashlib.sha256(CONFIG).hexdigest(),
            'original_initrd_sha256': hashlib.sha256(raw).hexdigest(),
            'original_initrd_size_bytes': len(raw),
            'original_ramdisk_prefix_preserved': True,
            'vendor_bootconfig_applied': False,
            'qualification': 'DIAGNOSTIC_CONFIGURATION_NOT_RUNTIME_PROOF'}
