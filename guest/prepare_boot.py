"""Prepare original ramdisk bytes for an isolated guest boot probe, never phone flash."""
import argparse
import hashlib
import json
from pathlib import Path
from tools.boot_metadata import inspect_image
from guest.ramdisk import inventory


def prepare(images, output):
    output=Path(output); output.mkdir(parents=True,exist_ok=True)
    reports={}; blobs={}
    for name in ('boot','vendor_boot'):
        image=Path(images)/(name+'.img')
        meta=inspect_image(image)
        size=meta['ramdisk_size_bytes']; offset=meta['ramdisk_offset']
        if not 0<size<=64*1024*1024: raise ValueError('Ramdisk size outside bounds')
        with image.open('rb') as stream:
            stream.seek(offset); blob=stream.read(size)
        if len(blob)!=size: raise ValueError('Truncated ramdisk')
        reports[name]={'sha256':hashlib.sha256(blob).hexdigest(),'size_bytes':size,
                       'inventory':inventory(blob)}
        blobs[name]=blob
    # Android vendor ramdisk precedes generic boot ramdisk. Do not edit guest files.
    combined=blobs['vendor_boot']+blobs['boot']
    (output/'original-initrd').write_bytes(combined)
    result={'source_firmware_build':'52168470052900520','original_ramdisks':reports,
            'combined_initrd_sha256':hashlib.sha256(combined).hexdigest(),
            'vendor_bootconfig_appended':False,
            'note':'Raw vendor+generic ramdisks only. No fstab/SELinux/userdata modification. Probe is not a production bootloader.'}
    (output/'ramdisk-report.json').write_text(json.dumps(result,indent=2)+'\n')
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--images',required=True,type=Path)
    p.add_argument('--output',required=True,type=Path)
    a=p.parse_args(); prepare(a.images,a.output)
