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
3. Verify the fixed OTA ZIP hash and reconstruct only boot/vendor_boot, validating
   payload operation and partition hashes. Inventory bounded CPIO ramdisks without
   extracting their paths on the runner. Hash equality is not signature verification.
4. Concatenate original vendor+generic ramdisk bytes without replacing `/init`.
   Vendor bootconfig is not yet appended; physical Qualcomm DTBs are not used.
5. Probe this original initramfs with the adapted kernel for at most 60 seconds.
   **No Android system disks are attached.** Full Android boot is not expected or
   claimed. Console markers distinguish kernel execution and original first-stage
   init, rather than treating QEMU startup or a successful workflow as a working OS.

The workflow publishes `analysis/builds/52168470052900520/guest-report.json` even
when compilation fails. Firmware images and source/build trees stay runner-local.
No successful compilation or guest execution should be inferred from these scripts.

## Local tests

```sh
python3 -m unittest discover -s guest/tests -v
```

Optional `lz4==4.4.4` enables the LZ4 fixture; Actions installs it. Subsequent work
requires the actual probe results, original fstab/partition mapping, a guest block
layout, hardware-service adaptation, graphics and IPC bridges. It also requires
an Android-hosted emulator and performance validation; none is supplied by this
kernel probe.
