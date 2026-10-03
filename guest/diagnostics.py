"""Opt-in offline diagnostic init configuration; never a replacement OS service.

Mirror AOSP LoadBootScripts imports, then launch the original logcat executable.
Only a fresh guest metadata filesystem is changed; original images remain intact.
"""
from pathlib import Path
import subprocess

IMPORTS=(
    '/system/etc/init/hw/init.rc','/system/etc/init','/system_ext/etc/init',
    '/vendor/etc/init','/odm/etc/init','/product/etc/init',
)


def configuration(label_overlay=False):
    prefix=('on early-init\n    mount none /metadata/vendor_file_contexts.metaport /vendor/etc/selinux/vendor_file_contexts bind\n\n' if label_overlay else '')
    text=prefix+'\n'.join('import '+path for path in IMPORTS)+'''

# Exclude kernel buffer to avoid a logcat -> kmsg -> logd feedback loop.
service metaport_bootlog /system/bin/logcat -b main -b system -b crash -v threadtime
    class core
    user logd
    group log
    disabled
    restart_period 5
    stdio_to_kmsg

on init
    start metaport_bootlog
'''
    if label_overlay: text=text.replace('on init\n    start metaport_bootlog\n','')
    return text


def install(metadata,work,label_overlay=False):
    metadata=Path(metadata);work=Path(work)
    if not metadata.is_file():raise ValueError('Expected fresh metadata image')
    source=work/'metaport-diagnostics.rc';source.write_text(configuration(label_overlay))
    # Paths are runner-generated. Do not construct debugfs commands from firmware text.
    if any(c in str(source) for c in '"\n\r'):
        raise ValueError('Unsupported generated path')
    for request in (f'write "{source}" /metaport-diagnostics.rc',
                    'ea_set /metaport-diagnostics.rc security.selinux u:object_r:metadata_file:s0'):
        subprocess.run(['debugfs','-w','-R',request,str(metadata)],check=True,
                       capture_output=True,timeout=30)
    result=subprocess.run(['debugfs','-R','cat /metaport-diagnostics.rc',str(metadata)],
                          check=True,capture_output=True,timeout=30)
    if result.stdout!=source.read_bytes():raise ValueError('Diagnostic config write/readback mismatch')
