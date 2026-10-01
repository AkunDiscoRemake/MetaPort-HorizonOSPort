#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-3.0-only
# Runs on the disposable GitHub runner, never on the user's phone.
set -euo pipefail
mkdir -p local-analysis/android-runtime
{
    df -h "$HOME" "$ANDROID_HOME"
    free -m
    "$ANDROID_HOME/emulator/emulator" -version
    "$ANDROID_HOME/emulator/emulator" -accel-check
    cat "$HOME/.android/avd/test.avd/config.ini"
} > local-analysis/android-runtime/emulator-host.txt 2>&1
# Capture early boot errors even if the test script never starts. Bounded lifetime;
# workflow cleanup terminates this logger after success or boot failure.
timeout 950s "$ANDROID_HOME/platform-tools/adb" logcat -v threadtime > local-analysis/android-runtime/boot-logcat.txt 2>&1 &
echo "$!" > local-analysis/android-runtime/boot-logger.pid
