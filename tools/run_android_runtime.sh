#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-3.0-only
# Run inside an already-booted emulator. Test fixtures, never a Horizon APK.
set -euo pipefail
mkdir -p local-analysis/android-runtime
trap 'timeout 15s adb logcat -d > local-analysis/android-runtime/logcat.txt 2>&1 || true' EXIT
adb shell setprop debug.checkjni 1
adb logcat -c
timeout 20m gradle -p port/android -PmetaportEmulatorTests=true :adapters:connectedDebugAndroidTest
