#!/usr/bin/env bash
# Called inside a disposable Linux runner; never writes to phone partitions.
set -euo pipefail
src=$(realpath "$1")
out=$(realpath -m "$2")
fragment=$(realpath "$3")
mkdir -p "$out"
patch_dir=$(dirname "$(realpath "$0")")
echo "$(cat "$patch_dir/platform-source.sha256")  $src/drivers/of/platform.c" | sha256sum --check --strict
patch --batch --fuzz=0 -d "$src" -p1 < "$patch_dir/boot-controller-alias.patch"
export PATH="/usr/lib/llvm-14/bin:$PATH"
args=("O=$out" ARCH=arm64 LLVM=1 LLVM_IAS=1
      CROSS_COMPILE=aarch64-linux-gnu- CROSS_COMPILE_COMPAT=arm-linux-gnueabi-
      CLANG_TRIPLE=aarch64-linux-gnu- REAL_CC=clang)
# Follow Meta's documented two-defconfig merge, then apply a separate guest delta.
KCONFIG_CONFIG="$out/.config" "$src/scripts/kconfig/merge_config.sh" -m -O "$out" \
  "$src/arch/arm64/configs/vendor/oculus_anorak_defconfig" \
  "$src/arch/arm64/configs/vendor/oculus_eureka_defconfig" "$fragment"
make -C "$src" "${args[@]}" olddefconfig
python3 - "$out/.config" <<'PY'
import pathlib,sys
text=pathlib.Path(sys.argv[1]).read_text()
required=['CONFIG_SERIAL_AMBA_PL011=y','CONFIG_SERIAL_AMBA_PL011_CONSOLE=y',
          'CONFIG_VIRTIO_MMIO=y','CONFIG_VIRTIO_BLK=y', 'CONFIG_BLK_DEV_INITRD=y',
          'CONFIG_RD_GZIP=y','CONFIG_RD_LZ4=y','CONFIG_ANDROID_BINDER_IPC=y',
          'CONFIG_ANDROID_BINDERFS=y','CONFIG_SECURITY_SELINUX=y']
missing=[line for line in required if line not in text.splitlines()]
if missing: raise SystemExit('Required guest config rejected by Kconfig: '+repr(missing))
PY
make -C "$src" "${args[@]}" -j"$(nproc)" Image
