"""Read boot/vendor_boot v3/v4 and kernel identity; never boot or flash an image.

Header layouts follow AOSP system/tools/mkbootimg/include/bootimg/bootimg.h.
This is metadata inspection, not a boot compatibility test or signature verifier.
"""
import hashlib
from pathlib import Path
import re
import struct
import zlib

MAX_KERNEL = 128 * 1024 * 1024
MAX_CONFIG = 1024 * 1024


def bounded_gzip(blob, limit):
    decoder = zlib.decompressobj(16 + zlib.MAX_WBITS)
    try:
        output = decoder.decompress(blob, limit + 1)
    except zlib.error as exc:
        raise ValueError('Invalid gzip stream') from exc
    if len(output) > limit or not decoder.eof:
        raise ValueError('Oversized or incomplete gzip stream')
    return output


def kernel_identity(blob):
    report = {'stored_size_bytes': len(blob), 'stored_sha256': hashlib.sha256(blob).hexdigest()}
    if blob.startswith(b'\x1f\x8b'):
        blob = bounded_gzip(blob, MAX_KERNEL)
        report['compression'] = 'gzip'
    elif len(blob) >= 60 and blob[56:60] == b'ARM\x64':
        report['compression'] = 'none_arm64_image'
    else:
        report['compression'] = 'UNKNOWN'
        report['status'] = 'UNSUPPORTED_KERNEL_ENCODING'
        return report
    version = re.search(rb'Linux version [0-9][^\x00\r\n]{1,511}', blob)
    report['linux_version_banner'] = version.group().decode('ascii', 'replace') if version else None
    report['uncompressed_size_bytes'] = len(blob)
    start = blob.find(b'IKCFG_ST')
    end = blob.find(b'IKCFG_ED', start + 8) if start >= 0 else -1
    report['embedded_config'] = 'NOT_FOUND'
    if start >= 0 and end > start:
        text = bounded_gzip(blob[start+8:end], MAX_CONFIG).decode('ascii', 'strict')
        selected = {}
        wanted = re.compile(r'CONFIG_(ANDROID_BINDER.*|VIRTIO.*|VIRTUALIZATION|KVM.*|ARCH_QCOM|ARCH_VIRT|'
                            r'DRM_MSM|DRM_VIRTIO_GPU|QCOM_SCM|SECURITY_SELINUX.*|DMABUF.*|'
                            r'DMA_SHARED_BUFFER|ASHMEM|ION|NAMESPACES|USER_NS|PID_NS|NET_NS|'
                            r'BINFMT_MISC|SERIAL_AMBA_PL011.*|ARM64_[0-9]+K_PAGES)')
        for line in text.splitlines():
            if '=' in line and not line.startswith('#'):
                key, value = line.split('=', 1)
                if wanted.fullmatch(key): selected[key] = value
            elif line.startswith('# CONFIG_') and line.endswith(' is not set'):
                key = line[2:-11]
                if wanted.fullmatch(key): selected[key] = 'not set'
        report.update(embedded_config='FOUND', selected_config=selected)
    report['status'] = 'IDENTITY_INSPECTED_NOT_BOOTED'
    return report


def inspect_image(path):
    path = Path(path)
    size = path.stat().st_size
    with path.open('rb') as stream:
        header = stream.read(4096)
        result = {'size_bytes': size, 'boot_tested': False, 'signature_verified': False}
        if header.startswith(b'ANDROID!'):
            if len(header) < 44: raise ValueError('Truncated Android boot header')
            version = struct.unpack_from('<I', header, 40)[0]
            result.update(image_format='ANDROID_BOOT', header_version=version)
            if version not in (3, 4):
                result['status'] = 'UNSUPPORTED_HEADER_VERSION'
                return result
            kernel_size, ramdisk_size, os_version, header_size = struct.unpack_from('<IIII', header, 8)
            minimum = 1584 if version == 4 else 1580
            if len(header) < minimum or not minimum <= header_size <= 4096:
                raise ValueError('Invalid boot header size')
            ramdisk_start = 4096 + ((kernel_size + 4095) // 4096) * 4096
            if kernel_size > MAX_KERNEL or ramdisk_start + ramdisk_size > size:
                raise ValueError('Boot payload range exceeds limits')
            result.update(status='HEADER_INSPECTED', kernel_size_bytes=kernel_size,
                          ramdisk_size_bytes=ramdisk_size, kernel_offset=4096,
                          ramdisk_offset=ramdisk_start, os_version_packed=os_version,
                          cmdline=header[44:1580].split(b'\0', 1)[0].decode('ascii', 'replace'))
            stream.seek(4096)
            result['kernel'] = kernel_identity(stream.read(kernel_size))
        elif header.startswith(b'VNDRBOOT'):
            if len(header) < 16: raise ValueError('Truncated vendor boot header')
            version, page_size = struct.unpack_from('<II', header, 8)
            result.update(image_format='VENDOR_BOOT', header_version=version)
            if version not in (3, 4):
                result['status'] = 'UNSUPPORTED_HEADER_VERSION'
                return result
            minimum = 2128 if version == 4 else 2112
            if len(header) < minimum: raise ValueError('Truncated vendor boot fields')
            header_size, dtb_size = struct.unpack_from('<II', header, 2096)
            ramdisk_size = struct.unpack_from('<I', header, 24)[0]
            if page_size < 2048 or page_size > 65536 or page_size & (page_size - 1) or header_size < minimum:
                raise ValueError('Invalid vendor boot geometry')
            align = lambda n: ((n + page_size - 1) // page_size) * page_size
            ramdisk_start = align(header_size)
            dtb_start = ramdisk_start + align(ramdisk_size)
            if dtb_start + dtb_size > size: raise ValueError('Vendor payload exceeds image')
            result.update(status='HEADER_INSPECTED', page_size=page_size,
                          ramdisk_size_bytes=ramdisk_size, ramdisk_offset=ramdisk_start,
                          dtb_size_bytes=dtb_size, dtb_offset=dtb_start,
                          cmdline=header[28:2076].split(b'\0',1)[0].decode('ascii','replace'),
                          board_name=header[2080:2096].split(b'\0',1)[0].decode('ascii','replace'))
            if version == 4:
                table_size, count, entry_size, bootconfig_size = struct.unpack_from('<IIII',header,2112)
                table_start = dtb_start + align(dtb_size)
                config_start = table_start + align(table_size)
                if count * entry_size > table_size or config_start + bootconfig_size > size:
                    raise ValueError('Vendor ramdisk table exceeds image')
                result.update(ramdisk_fragment_count=count, ramdisk_table_size_bytes=table_size,
                              bootconfig_size_bytes=bootconfig_size)
        elif header.startswith(b'\x7fELF'):
            if len(header) < 20 or header[4] not in (1, 2) or header[5] not in (1, 2): raise ValueError('Invalid ELF identity')
            result.update(image_format='ELF', elf_class=header[4],
                          machine=struct.unpack_from('<H' if header[5] == 1 else '>H',header,18)[0],
                          status='ELF_IDENTITY_ONLY')
        elif header.startswith(b'AVB0'):
            result.update(image_format='AVB_VBMETA', status='MAGIC_ONLY')
        else:
            result.update(image_format='UNKNOWN', status='NOT_INTERPRETED')
        return result
