"""Targeted offline inspection of boot HAL and account/Store dependencies.

Never executes firmware, authenticates, contacts Meta, or obtains credentials.
Uses verified partition images and the fixed build's existing filesystem inventory.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import tempfile
from tools.scan_partitions import command,dump_entry,elf_report

BOOT_ELF={
    '/bin/hw/android.hardware.boot@1.2-service',
    '/lib64/hw/android.hardware.boot@1.0-impl-1.2-qti.so',
    '/lib64/hw/bootctrl.anorak.so',
}
CONFIG={
    '/etc/init/android.hardware.boot@1.2-service.rc',
    '/etc/vintf/manifest/android.hardware.boot@1.2.xml',
    '/etc/init/hw/init.anorak.rc',
}
POLICY={'system':{'/system/etc/selinux/plat_file_contexts'},'vendor':{'/etc/selinux/vendor_file_contexts'}}
APKS={'/app/Store/Store.apk','/priv-app/DeviceAuthServer/DeviceAuthServer.apk',
      '/app/AccountsCenterPWA/AccountsCenterPWA.apk'}


def select(entries,paths):
    chosen={e['path']:e for e in entries if e['path'] in paths and e['kind']=='file'}
    if set(chosen)!=paths: raise ValueError('Missing required inventory paths: '+repr(paths-set(chosen)))
    return chosen


def inspect(images,output):
    inventory=json.loads(Path('analysis/builds/52168470052900520/static-analysis.json').read_text())['partitions']
    reconstruction=json.loads(Path(images).parent.joinpath('reconstruction.json').read_text())['partitions']
    result={'firmware_build':'52168470052900520','firmware_executed_by_this_inspector':False,
            'meta_servers_contacted':False,'login_tested':False,'store_functional':False,
            'boot_hal':[],'configuration':[],'applications':[],'device_label_rules':[]}
    for partition,paths in [('vendor',BOOT_ELF|CONFIG|POLICY['vendor']),('system',POLICY['system']),('system_ext',APKS)]:
        image=Path(images)/(partition+'.img')
        with image.open('rb') as stream:
            digest=hashlib.file_digest(stream,'sha256').hexdigest() if hasattr(hashlib,'file_digest') else None
        if digest is None:
            h=hashlib.sha256()
            with image.open('rb') as stream:
                while chunk:=stream.read(1024*1024):h.update(chunk)
            digest=h.hexdigest()
        if digest!=reconstruction[partition]['sha256']: raise ValueError('Partition hash mismatch')
        chosen=select(inventory[partition]['entries'],paths)
        for path,entry in sorted(chosen.items()):
            with tempfile.TemporaryDirectory() as tmp:
                binary=Path(tmp)/'component';dump_entry(image,entry,binary)
                if path in BOOT_ELF:
                    report=elf_report(binary,deep=True)
                    # Keep relevant path/diagnostic strings, not arbitrary rodata.
                    report.pop('rodata_hex',None)
                    report['dependency_strings']=sorted(set(m.group().decode('ascii') for m in
                        re.finditer(rb'[ -~]{5,300}',binary.read_bytes()) if re.search(
                            rb'/dev/|/sys/|bootctrl|bootdevice|slot|gpt|partition|failed|error|misc|ufshc',m.group(),re.I)))[:200]
                    result['boot_hal'].append({'path':path,**report})
                elif path in POLICY.get(partition,set()):
                    raw=binary.read_bytes()
                    result['device_label_rules'].append({'path':path,'sha256':hashlib.sha256(raw).hexdigest(),
                        'rules':[line for line in raw.decode().splitlines() if re.search(r'/dev/block|misc_block_device|vd_device|boot_block_device',line)]})
                elif path in CONFIG:
                    if binary.stat().st_size>256*1024:raise ValueError('Oversized config')
                    raw=binary.read_bytes()
                    result['configuration'].append({'path':path,'sha256':hashlib.sha256(raw).hexdigest(),
                                                     'text':raw.decode('utf-8')})
                else:
                    manifest,_=command(['aapt','dump','xmltree',str(binary),'AndroidManifest.xml'],max_output=2*1024*1024)
                    badging,_=command(['aapt','dump','badging',str(binary)],max_output=512*1024)
                    result['applications'].append({'path':path,'sha256':hashlib.sha256(binary.read_bytes()).hexdigest(),
                         'size_bytes':binary.stat().st_size,'manifest':manifest,'badging':badging,
                         'installed_or_executed':False})
    Path(output).write_text(json.dumps(result,indent=2)+'\n')


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--images',required=True);p.add_argument('--output',required=True)
    a=p.parse_args();inspect(a.images,a.output)
