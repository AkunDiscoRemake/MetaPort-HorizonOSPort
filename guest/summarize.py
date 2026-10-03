"""Publish bounded, honest build/probe evidence through the repository API path."""
import hashlib
import json
import os
from pathlib import Path

root=Path(os.environ['GUEST_WORK'])
report_dir=root/'reports'; report_dir.mkdir(parents=True,exist_ok=True)
build_log=root/'build.log'
image=root/'kernel-out/arch/arm64/boot/Image'
report={'source':json.loads(Path('guest/kernel/source.json').read_text()),
        'kernel_patch_sha256':hashlib.sha256(Path('guest/kernel/boot-controller-alias.patch').read_bytes()).hexdigest(),
        'workflow_run':os.environ['GITHUB_RUN_ID'],'project_commit':os.environ['GITHUB_SHA'],
        'build_step_outcome':os.environ.get('BUILD_OUTCOME','unknown'),
        'ramdisk_step_outcome':os.environ.get('RAMDISK_OUTCOME','unknown'),
        'storage_step_outcome':os.environ.get('STORAGE_OUTCOME','unknown'),
        'probe_step_outcome':os.environ.get('PROBE_OUTCOME','unknown'),
        'kernel_cache_hit':os.environ.get('KERNEL_CACHE_HIT')=='true',
        'port_status':'NOT PORTED YET','physical_phone_tested':False,
        'build_log_tail':'\n'.join(build_log.read_text(errors='replace').splitlines()[-120:]) if build_log.exists() else None}
if image.exists(): report['kernel_image']={'sha256':hashlib.sha256(image.read_bytes()).hexdigest(),'size_bytes':image.stat().st_size}
config=root/'kernel-out/.config'
if config.exists():
    keys=('CONFIG_VIRTIO','CONFIG_SERIAL_AMBA','CONFIG_ANDROID_BINDER','CONFIG_SECURITY_SELINUX','CONFIG_LOCALVERSION','CONFIG_LTO','CONFIG_CFI','CONFIG_FTRACE','CONFIG_TRACING','CONFIG_EVENT_TRACING','CONFIG_TRACEPOINTS','CONFIG_TP_PRINTK','CONFIG_BOOT_CONFIG','CONFIG_BOOTTIME_TRACING')
    report['selected_build_config']=[l for l in config.read_text().splitlines() if any(k in l for k in keys)]
for name,path in [('security_contract',root/'security-contract.json'),('integration',root/'integration-report.json'),('storage',root/'storage/storage-report.json'),('ramdisk',root/'ramdisks/ramdisk-report.json'),('probe',root/'probe/probe-report.json')]:
    if path.exists(): report[name]=json.loads(path.read_text())
(report_dir/'guest-report.json').write_text(json.dumps(report,indent=2)+'\n')
