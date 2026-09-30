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


def child_limits():
    resource.setrlimit(resource.RLIMIT_CORE,(0,0))
    resource.setrlimit(resource.RLIMIT_FSIZE,(8*1024*1024,8*1024*1024))


def classify(text):
    return {
        'kernel_console_observed':bool(re.search(r'Booting Linux on physical CPU|Linux version [0-9]',text)),
        'original_init_exec_attempt_observed':'Run /init as init process' in text,
        'init_sigill_observed':'Attempted to kill init! exitcode=0x00000004' in text,
        'original_init_marker_observed':bool(re.search(r'init:.*(?:init first stage started|First stage mount|first_stage)',text,re.I)),
        'kernel_panic_observed':'Kernel panic' in text,
        'android_boot_completed':False,
        'qualification':'Kernel/first-stage probe only; no Android system disks supplied, no full OS boot claim.'
    }


def probe(kernel,initrd,output):
    kernel=Path(kernel).resolve(); initrd=Path(initrd).resolve(); output=Path(output)
    output.mkdir(parents=True,exist_ok=True)
    args=['qemu-system-aarch64','-nodefaults','-no-user-config','-machine','virt,gic-version=3',
          '-accel','tcg','-cpu','max','-smp','2','-m','1024',
          '-display','none','-serial','stdio','-monitor','none','-nic','none',
          '-no-reboot','-sandbox','on,obsolete=deny,elevateprivileges=deny,spawn=deny,resourcecontrol=deny',
          '-kernel',str(kernel),'-initrd',str(initrd),
          '-append','console=ttyAMA0 earlycon=pl011,0x9000000 rdinit=/init panic=-1']
    log=output/'guest-console.log'
    timed_out=False
    with log.open('wb') as stream:
        proc=subprocess.Popen(args,stdin=subprocess.DEVNULL,stdout=stream,stderr=subprocess.STDOUT,
                              start_new_session=True,preexec_fn=child_limits)
        try: proc.wait(timeout=60)
        except subprocess.TimeoutExpired:
            timed_out=True
            os.killpg(proc.pid,signal.SIGTERM)
            try: proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                os.killpg(proc.pid,signal.SIGKILL); proc.wait()
    text=log.read_text(errors='replace')
    result={'qemu_returncode':proc.returncode,'timeout':timed_out,
            'kernel_sha256':hashlib.sha256(kernel.read_bytes()).hexdigest(),
            'initrd_sha256':hashlib.sha256(initrd.read_bytes()).hexdigest(),
            'network_enabled':False,'kvm_used':False,'phone_modified':False,
            'command':args,'console_tail':'\n'.join(text.splitlines()[-300:]),**classify(text)}
    (output/'probe-report.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k!='console_tail'},indent=2))
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--kernel',required=True);p.add_argument('--initrd',required=True);p.add_argument('--output',required=True)
    a=p.parse_args(); result=probe(a.kernel,a.initrd,a.output)
    if not result['kernel_console_observed']: raise SystemExit(1)
