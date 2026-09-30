"""Describe the real emulated virtio controller under a guest soc bus.

Matches original init's /dev/block/platform/soc/${ro.boot.bootdevice} path without
changing its scripts or pretending virtio implements Qualcomm UFS ioctls.
"""
from pathlib import Path
import re
import subprocess


def relocate_virtio(dts):
    pattern=r'(?m)^\tvirtio_mmio@a000000 \{\n[^{}]*?^\t\};'
    matches=list(re.finditer(pattern,dts))
    if len(matches)!=1 or re.search(r'(?m)^\tsoc(?:@[^ ]+)? \{',dts):
        raise ValueError('Unexpected QEMU DT structure; refuse ambiguous transformation')
    node=matches[0].group()
    replacement=('\tsoc {\n\t\tcompatible = "simple-bus";\n'
                 '\t\t#address-cells = <0x02>;\n\t\t#size-cells = <0x02>;\n'
                 '\t\tranges;\n'+''.join('\t'+line+'\n' for line in node.splitlines())+'\t};')
    return dts[:matches[0].start()]+replacement+dts[matches[0].end():]


def prepare(output):
    output=Path(output);output.mkdir(parents=True,exist_ok=True)
    raw=output/'qemu.dtb';text=output/'qemu.dts';adapted=output/'guest.dts';result=output/'guest.dtb'
    subprocess.run(['qemu-system-aarch64','-nodefaults','-no-user-config','-display','none','-nic','none',
        '-machine',f'virt,gic-version=3,dumpdtb={raw}','-accel','tcg','-cpu','max','-smp','2','-m','1024'],check=True,timeout=30)
    subprocess.run(['dtc','-I','dtb','-O','dts','-o',str(text),str(raw)],check=True,timeout=30,capture_output=True)
    adapted.write_text(relocate_virtio(text.read_text()))
    subprocess.run(['dtc','-I','dts','-O','dtb','-o',str(result),str(adapted)],check=True,timeout=30,capture_output=True)
    return result
