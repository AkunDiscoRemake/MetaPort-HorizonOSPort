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
from guest.dtb import prepare as prepare_dtb


def child_limits():
    resource.setrlimit(resource.RLIMIT_CORE,(0,0))
    resource.setrlimit(resource.RLIMIT_FSIZE,(8*1024**3,8*1024**3))



def security_observations(text):
    """Preserve early startup errors rather than only the final retry loop."""
    pattern=re.compile(r'keystore|keymint|keymaster|qsee|secureclock|sharedsecret|wrappedkey|encryptFstab|dm-default-key',re.I)
    events=[];counts={};matched=0;omitted=0
    for line in text.splitlines():
        if not pattern.search(line):continue
        matched+=1
        signature=re.sub(r'^\s*\[[^]]+\]\s*','',line)
        counts[signature]=counts.get(signature,0)+1
        if counts[signature]<=3 and len(events)<160:events.append(line[:1024])
        else:omitted+=1
    return {'events':events,'matching_line_count':matched,'omitted_line_count':omitted,
            'keystore_start_attempt_observed':"starting service 'keystore2'" in text,
            'keymint_start_attempt_observed':"starting service 'vendor.keymint-qti'" in text,
            'keystore_service_wait_observed':bool(re.search(r'Waited .* for android\.system\.keystore2\.IKeystoreService/default',text)),
            'userdata_encryption_request_observed':bool(re.search(r'Calling: .*vdc cryptfs encryptFstab .*userdata /data',text)),
            'keystore_registered': 'NOT_ESTABLISHED',
            'userdata_mounted':'NOT_ESTABLISHED',
            'root_cause':'NOT_ESTABLISHED_FROM_LOG_MATCHES'}



def signal_trace_parameters(enabled):
    # Verified against kernel/trace/{trace,trace_events}.c in the pinned kernel.
    # Trace metadata only, not registers, memory, keys, or decrypted storage.
    if type(enabled) is not bool:raise ValueError('Signal trace flag must be boolean')
    return 'trace_event=signal:signal_generate,sched:sched_process_exit tp_printk' if enabled else ''


def signal_observations(text):
    events=[];generated=[];exits=[];total=0
    security_events=[];security_generated=[];security_exits=[];security_count=0
    service_pattern=re.compile(r"started service '(keystore2|vendor.keymint-qti|vendor.qseecomd|qseecom-service)' has pid (\d+)")
    service_pids={int(pid):name for name,pid in service_pattern.findall(text)}
    pattern=re.compile(r'signal_generate: sig=(-?\d+) errno=(-?\d+) code=(-?\d+) comm=(.*?) pid=(\d+) grp=(\d+) res=(\d+)')
    exit_pattern=re.compile(r'sched_process_exit: comm=(.*?) pid=(\d+) prio=(-?\d+)')
    for line in text.splitlines():
        signal_match=pattern.search(line);exit_match=exit_pattern.search(line)
        if not signal_match and not exit_match:continue
        total+=1
        if signal_match:
            sig,error,code,comm,pid,group,result=signal_match.groups()
            record={'signal':int(sig),'errno':int(error),'si_code':int(code),
                    'target_comm':comm[:64],'target_pid':int(pid),
                    'group':int(group),'generation_result':int(result)}
        else:
            comm,pid,priority=exit_match.groups()
            record={'comm':comm[:64],'pid':int(pid),'priority':int(priority)}
        if len(events)<200:
            events.append(line[:1024])
            (generated if signal_match else exits).append(record)
        # Preserve late security failures even if unrelated early SIGCHLD/exit
        # events fill the generic sample. PID/name association is evidence only.
        binder=re.fullmatch(r'binder:(\d+)_\d+',comm)
        relevant=(int(pid) in service_pids or comm=='keystore2' or
                  (binder is not None and int(binder.group(1)) in service_pids))
        if relevant:
            security_count+=1
            if len(security_events)<80:
                security_events.append(line[:1024])
                (security_generated if signal_match else security_exits).append(record)
    return {'events':events,'event_count':total,'events_truncated':total>len(events),
            'generated_signals':generated,'process_exits':exits,
            'security_events':security_events,'security_event_count':security_count,
            'security_events_truncated':security_count>len(security_events),
            'security_generated_signals':security_generated,'security_process_exits':security_exits,
            'service_pid_candidates':service_pids,
            'trace_observed':bool(total),'fatal_cause':'NOT_ESTABLISHED_BY_SIGNAL_GENERATION'}


def classify(text):
    lines=text.splitlines()
    block_denials=[line for line in lines if 'avc:' in line and 'denied' in line and
        'scontext=u:r:hal_bootctl_default:s0' in line and 'tcontext=u:object_r:vd_device:s0' in line]
    return {
        'kernel_console_observed':bool(re.search(r'Booting Linux on physical CPU|Linux version [0-9]',text)),
        'recovery_mount_skip_observed':'First stage mount skipped (recovery mode)' in text,
        'original_init_exec_attempt_observed':'Run /init as init process' in text,
        'init_sigill_observed':'Attempted to kill init! exitcode=0x00000004' in text,
        'original_init_marker_observed':bool(re.search(r'init:.*(?:init first stage started|First stage mount|first_stage)',text,re.I)),
        'bootcontrol_events':[line for line in text.splitlines() if re.search(
            r'boot-hal|bootctrl|IBootControl|libgpt|gpt-utils|boot_control|Failed to load.*boot|metaport_bootlog|misc.*(?:fail|denied)|avc:.*(?:boot|logcat|logpersist)',line,re.I)][:100],
        'diagnostic_events':[line for line in text.splitlines() if re.search(r'metaport|init_rc|logcat|stdio_to_kmsg',line,re.I)][:80],
        'controller_alias_observed':'MetaPort: virtio boot controller alias 1d84000.ufshc' in text,
        'bootcontrol_hidl12_client_observed':'Using HIDL version 1.2 of IBootControl' in text,
        'post_fs_data_observed':bool(re.search(r'action=post-fs-data|processing action \(post-fs-data\)',text)),
        'zygote_start_attempt_observed':"starting service 'zygote'" in text,
        'zygote_termination_observed':bool(re.search(r"Service 'zygote'.*(?:received signal|exited with status)",text)),
        'storage_events':[line for line in lines if re.search(r'userdata|checkpoint needsCheckpoint|mount_all.*late|/data.*(?:Read-only|failed)|(?:Failed|Unable|Cannot).*userdata',line)][:80],
        'security_startup':security_observations(text),
        'signal_trace':signal_observations(text),
        'second_stage_init_observed':'init second stage started!' in text,
        'logical_partitions_created':re.findall(r'Created logical partition ([A-Za-z0-9_]+) on device',text),
        'boot_events':[line for line in text.splitlines() if any(token in line for token in (
            'init first stage started','init second stage started','Switching root',
            'Created logical partition','__mount(','Loading SELinux policy',
            'SELinux: Loaded policy','AvbHandle','vbmeta digest','dm-verity',
            'DSU not detected','starting service'))][:180],
        'label_overlay_mount_failed':any('mount none /metadata/vendor_file_contexts.metaport' in line and 'failed:' in line for line in text.splitlines()),
        # vda3 is misc in the generated GPT; whole-disk vda is a distinct role.
        'bootcontrol_misc_label_denial_observed':any(re.search(r'(?:path="/dev/block/vda3"|name="vda3")',line) for line in block_denials),
        'bootcontrol_disk_label_denial_observed':any(re.search(r'(?:path="/dev/block/vda"|name="vda")',line) for line in block_denials),
        'diagnostic_logger_denied_observed':any('avc:' in line and 'denied' in line and
            'scontext=u:r:init:s0' in line and 'tcontext=u:object_r:logcat_exec:s0' in line for line in text.splitlines()),
        'kernel_panic_observed':'Kernel panic' in text,
        'android_boot_completed':False,
        'qualification':'Boot-stage evidence only; no full Android/Horizon boot claim.'
    }


def probe(kernel,initrd,output,disk=None,trace_signals=False):
    kernel=Path(kernel).resolve(); initrd=Path(initrd).resolve(); output=Path(output)
    output.mkdir(parents=True,exist_ok=True)
    diagnostic=False
    args=['qemu-system-aarch64','-nodefaults','-no-user-config','-machine','virt,gic-version=3',
          '-accel','tcg','-cpu','max','-smp','2','-m','1024',
          '-display','none','-serial','stdio','-monitor','none','-nic','none',
          '-no-reboot','-sandbox','on,obsolete=deny,elevateprivileges=deny,spawn=deny,resourcecontrol=deny',
          '-kernel',str(kernel),'-initrd',str(initrd),
          '-append','console=ttyAMA0 earlycon=pl011,0x9000000 rdinit=/init panic=-1 printk.devkmsg=on loglevel=8 '
          'androidboot.hardware=eureka androidboot.slot_suffix=_a androidboot.force_normal_boot=1']
    trace_options=signal_trace_parameters(trace_signals)
    if trace_options:args[-1]+=' '+trace_options
    if disk is not None:
        disk=Path(disk).resolve()
        if not disk.is_file() or disk.stat().st_size>8*1024**3:
            raise ValueError('Expected bounded regular guest disk image')
        avb=json.loads((disk.parent/'avb-boot.json').read_text())
        if avb['hash_alg']!='sha256' or not re.fullmatch('[0-9a-f]{64}',avb['digest']) or not 0<avb['size']<=16*1024*1024:
            raise ValueError('Invalid bounded vbmeta boot parameters')
        args[-1]+=' androidboot.boot_devices=soc/1d84000.ufshc androidboot.bootdevice=1d84000.ufshc'
        args[-1]+=f" androidboot.vbmeta.hash_alg=sha256 androidboot.vbmeta.size={avb['size']} androidboot.vbmeta.digest={avb['digest']}"
        storage=json.loads((disk.parent/'storage-report.json').read_text())
        diagnostic=storage.get('diagnostic_init_rc',False)
        if diagnostic: args[-1]+=' androidboot.init_rc=/metadata/metaport-diagnostics.rc'
        dtb=prepare_dtb(output/'device-tree')
        args+=['-dtb',str(dtb)]
        args+=['-drive',f'if=none,id=guestdisk,file={disk},format=raw,snapshot=on',
               '-device','virtio-blk-device,drive=guestdisk,bus=virtio-mmio-bus.0']
    log=output/'guest-console.log'
    timed_out=False
    with log.open('wb') as stream:
        proc=subprocess.Popen(args,stdin=subprocess.DEVNULL,stdout=stream,stderr=subprocess.STDOUT,
                              start_new_session=True,preexec_fn=child_limits)
        deadline=time.monotonic()+180
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
    result={'signal_trace_requested':trace_signals,'diagnostic_init_rc':diagnostic,'guest_dtb_sha256':hashlib.sha256(dtb.read_bytes()).hexdigest() if disk else None,
            'guest_disk_attached':disk is not None,'disk_writes':'disposable QEMU snapshot' if disk else None,
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
    p.add_argument('--trace-signals',action='store_true',help='Guest-kernel signal/lifecycle tracepoints; no ptrace or policy relaxation')
    a=p.parse_args(); result=probe(a.kernel,a.initrd,a.output,a.disk,a.trace_signals)
    if not result['kernel_console_observed']: raise SystemExit(1)
