# Original-firmware guest boot research

**NOT PORTED YET.** This is not an APK, substitute launcher, or completed Horizon OS boot.

The phone's bootloader remains locked. Everything here runs in a disposable Ubuntu
Actions runner using QEMU TCG, without KVM, guest networking, host-drive passthrough,
or phone access. No Quest firmware should ever be flashed onto the Infinix.

## Experiment

1. Obtain the official public Meta kernel snapshot pinned in `kernel/source.json`.
   It is Linux 5.10.240 but belongs to publication **5227074.3810.520**, not the OTA
   **52168470052900520**. An exact source match has **not** been established.
2. Merge Meta's documented anorak/eureka configurations with `kernel/virt.config`.
   Add virtual-device support missing from the unchanged firmware kernel; disable
   toolchain-dependent CFI/LTO/SCS for this experimental distro-LLVM build. This
   changes security/performance properties and is not a production configuration.
3. Verify the fixed OTA ZIP hash and reconstruct boot/vendor_boot, the seven logical filesystems and vbmeta images, validating
   payload operation and partition hashes. Inventory bounded CPIO ramdisks without
   extracting their paths on the runner. Hash equality is not signature verification.
4. Concatenate original vendor+generic ramdisk bytes without replacing `/init`.
   Vendor bootconfig is not yet appended; physical Qualcomm DTBs are not used.
   Explicit guest cmdline selects eureka hardware identity, slot `_a` and normal boot;
   it does not assert AVB success, unlock the phone, or replace original init.
5. Build a disposable GPT disk with original filesystem bytes in Android LP
   metadata, original vbmeta blocks and a fresh empty metadata filesystem. Derive
   vbmeta digest/size handoff parameters without disabling guest verification.
   This is not a hardware trust anchor or rollback implementation.
The layout also includes fresh `misc` and two copies of the original boot image
   as boot_a/boot_b. This does not implement bootloader slot selection or report
   successful boot. `dtb.py` places the emulated virtio controller under a simple
   soc bus to match original bootdevice path construction, not to emulate UFS ioctls.
6. Probe this original initramfs with the adapted kernel and disk for at most
   180 seconds. Writes use a temporary QEMU snapshot; no host devices are attached.
   Full Android/Horizon boot is not claimed. Console markers distinguish kernel execution and original first-stage
   init, rather than treating QEMU startup or a successful workflow as a working OS.

The workflow publishes `analysis/builds/52168470052900520/guest-report.json` even
when compilation fails. Firmware images and source/build trees stay runner-local.
Measured results, including original second-stage execution and outstanding
BootControl/data/hardware blockers, are recorded in
[the storage experiment report](../analysis/builds/52168470052900520/GUEST-STORAGE.md).
A successful workflow alone is not evidence of full Android boot.

## Local tests

```sh
python3 -m unittest discover -s guest/tests -v
```

Optional `lz4==4.4.4` enables the LZ4 fixture; Actions installs it. Subsequent work
requires BootControl/slot-state and data-storage adaptation, original hardware-service
adaptation, graphics and IPC bridges. A system-disk layout now exists, including optional blank userdata. Filesystem/encryption provisioning,
TEE functionality and physical hardware integration are not working. It also requires
an Android-hosted emulator and performance validation; none is supplied by this
kernel probe.

## Experimental diagnostics (not enabled by default)

`storage.py --diagnostics` currently prepares the label-overlay experiment and an
init configuration importing the original boot scripts. The attempt to bind the
new labels was denied, and the direct logcat attempt was also denied by SELinux.
Generated label entries are **not evidence of applied labels**. See
[measured failures](../analysis/builds/52168470052900520/BOOTCONTROL-LABELS.md).
The ordinary workflow does not select this failed overlay. SELinux/AVB remain enabled.

## Boot-controller namespace compatibility

The pinned kernel now applies `kernel/boot-controller-alias.patch` after an exact
source-file hash check. Only the explicitly marked virtio MMIO controller under
`/soc` on `metaport,virt` gets the platform name `1d84000.ufshc`. Resources and
protocol remain virtio, not UFS. This lets original ueventd partition-role rules
match without a policy overlay. Run 36719412359 activated the alias, reached
post-fs-data and observed an original client obtaining HIDL BootControl 1.2.
Whole-disk access denials, missing writable data and restarting services remain.
See [measured results and limits](../analysis/builds/52168470052900520/BOOT-CONTROLLER-ALIAS.md).

## Optional fresh userdata experiment

`guest/storage.py --userdata-mib 1024` appends a blank 1 GiB guest partition,
without moving the existing GPT roles or preformatting an unencrypted replacement.
The original fs_mgr/vold and encryption policy remain responsible for provisioning.
The workflow now selects this experiment; the builder default remains disabled.

Run 36761552459 reached the original `cryptfs encryptFstab` request and then waited
for the unavailable Keystore2 service until the probe timeout. It did **not**
reach post-fs-data or Zygote in this run, unlike the earlier no-userdata probe.
See [measured userdata results](../analysis/builds/52168470052900520/GUEST-USERDATA.md).
This is not a mounted-data, full-boot or phone-compatibility claim.
