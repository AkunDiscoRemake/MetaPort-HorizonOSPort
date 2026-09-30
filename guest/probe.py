"""Run a time-bounded QEMU TCG probe. No host drives, network, KVM or phone access."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import resource
import signal
import subprocess
import time


def child_limits():
    resource.setrlimit(resource.RLIMIT_CORE,(0,0))
    resource.setrlimit(resource.RLIMIT_FSIZE,(8*1024**3,8*1024**3))


def classify(text):
    return {
        'kernel_console_observed':bool(re.search(r'Booting Linux on physical CPU|Linux version [0-9]',text)),
        'recovery_mount_skip_observed':'First stage mount skipped (recovery mode)' in text,
        'original_init_exec_attempt_observed':'Run /init as init process' in text,
        'init_sigill_observed':'Attempted to kill init! exitcode=0x00000004' in text,
        'original_init_marker_observed':bool(re.search(r'init:.*(?:init first stage started|First stage mount|first_stage)',text,re.I)),
        'kernel_panic_observed':'Kernel panic' in text,
        'android_boot_completed':False,
        'qualification':'Boot-stage evidence only; no full Android/Horizon boot claim.'
    }


def probe(kernel,initrd,output,disk=None):
    kernel=Path(kernel).resolve(); initrd=Path(initrd).resolve(); output=Path(output)
    output.mkdir(parents=True,exist_ok=True)
    args=['qemu-system-aarch64','-nodefaults','-no-user-config','-machine','virt,gic-version=3',
          '-accel','tcg','-cpu','max','-smp','2','-m','1024',
          '-display','none','-serial','stdio','-monitor','none','-nic','none',
          '-no-reboot','-sandbox','on,obsolete=deny,elevateprivileges=deny,spawn=deny,resourcecontrol=deny',
          '-kernel',str(kernel),'-initrd',str(initrd),
          '-append','console=ttyAMA0 earlycon=pl011,0x9000000 rdinit=/init panic=-1 printk.devkmsg=on loglevel=8 '
          'androidboot.hardware=eureka androidboot.slot_suffix=_a androidboot.force_normal_boot=1']
    if disk is not None:
        disk=Path(disk).resolve()
        if not disk.is_file() or disk.stat().st_size>8*1024**3:
            raise ValueError('Expected bounded regular guest disk image')
        avb=json.loads((disk.parent/'avb-boot.json').read_text())
        if avb['hash_alg']!='sha256' or not re.fullmatch('[0-9a-f]{64}',avb['digest']) or not 0<avb['size']<=16*1024*1024:
            raise ValueError('Invalid bounded vbmeta boot parameters')
        args[-1]+=' androidboot.boot_devices=a000000.virtio_mmio'
        args[-1]+=f" androidboot.vbmeta.hash_alg=sha256 androidboot.vbmeta.size={avb['size']} androidboot.vbmeta.digest={avb['digest']}"
        args+=['-drive',f'if=none,id=guestdisk,file={disk},format=raw,snapshot=on',
               '-device','virtio-blk-device,drive=guestdisk,bus=virtio-mmio-bus.0']
    log=output/'guest-console.log'
    timed_out=False
    with log.open('wb') as stream:
        proc=subprocess.Popen(args,stdin=subprocess.DEVNULL,stdout=stream,stderr=subprocess.STDOUT,
                              start_new_session=True,preexec_fn=child_limits)
        deadline=time.monotonic()+90
        while proc.poll() is None:
            if time.monotonic()>=deadline or log.stat().st_size>8*1024*1024:
                timed_out=time.monotonic()>=deadline
                os.killpg(proc.pid,signal.SIGTERM)
                try: proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    os.killpg(proc.pid,signal.SIGKILL);proc.wait()
                break
            try: proc.wait(timeout=0.25)
            except subprocess.TimeoutExpired: pass
    with log.open('rb') as stream: text=stream.read(8*1024*1024).decode(errors='replace')
    result={'guest_disk_attached':disk is not None,'disk_writes':'disposable QEMU snapshot' if disk else None,
            'console_limit_exceeded':log.stat().st_size>8*1024*1024,
            'qemu_returncode':proc.returncode,'timeout':timed_out,
            'kernel_sha256':hashlib.sha256(kernel.read_bytes()).hexdigest(),
            'initrd_sha256':hashlib.sha256(initrd.read_bytes()).hexdigest(),
            'network_enabled':False,'kvm_used':False,'phone_modified':False,
            'command':args,'console_head':'\n'.join(text.splitlines()[:100]),'console_tail':'\n'.join(text.splitlines()[-300:]),**classify(text)}
    (output/'probe-report.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k not in ('console_tail','console_head')},indent=2))
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--kernel',required=True);p.add_argument('--initrd',required=True);p.add_argument('--output',required=True)
    p.add_argument('--disk')
    a=p.parse_args(); result=probe(a.kernel,a.initrd,a.output,a.disk)
    if not result['kernel_console_observed']: raise SystemExit(1)
