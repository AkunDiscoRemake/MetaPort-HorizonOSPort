# SPDX-License-Identifier: GPL-3.0-only
"""Supervise the disposable Android test emulator, capturing host launch failures.

Default command runs project adapter tests only. Explicit callbacks may run an
isolated original-APK baseline. A boot failure is never a test success.
"""
import argparse
import os
from pathlib import Path
import signal
import subprocess
import threading
import time


def configure(text):
    values = {'hw.cpu.ncore':'2', 'hw.ramSize':'2048', 'vm.heapSize':'512',
              'disk.dataPartition.size':'2048M'}
    lines = [line for line in text.splitlines() if line.partition('=')[0].strip() not in values]
    return '\n'.join(lines + [f'{k}={v}' for k,v in values.items()]) + '\n'


def capture(stream, destination, limit=1024*1024):
    """Drain throughout process lifetime, but persist at most limit bytes."""
    saved = 0
    with Path(destination).open('wb') as out:
        while True:
            block = stream.read1(4096)
            if not block:
                break
            keep = block[:max(0, limit-saved)]
            out.write(keep)
            out.flush()
            saved += len(keep)


def wait_for_boot(process, adb, timeout):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        code = process.poll()
        if code is not None:
            raise RuntimeError(f'Emulator exited before boot (exit {code}); see emulator-output.txt')
        try:
            result = subprocess.run([str(adb), '-s', 'emulator-5554', 'shell',
                                     'getprop', 'sys.boot_completed'], capture_output=True, timeout=10)
            if result.returncode == 0 and result.stdout.strip() == b'1':
                return
        except subprocess.TimeoutExpired:
            pass
        time.sleep(2)
    raise TimeoutError('Emulator boot deadline exceeded; no instrumentation executed')


def run(api, sdk, output, boot_timeout=600, test_command=None):
    if api not in (29, 35) or not 1 <= boot_timeout <= 900:
        raise ValueError('Unsupported test configuration')
    sdk = Path(sdk)
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    adb = sdk/'platform-tools/adb'
    subprocess.run([str(sdk/'cmdline-tools/latest/bin/avdmanager'), 'create', 'avd',
                    '--force', '--name', 'test', '--package',
                    f'system-images;android-{api};google_apis;x86_64', '--device', 'pixel_2'],
                   input='no\n', text=True, check=True, timeout=120)
    avds = Path(os.environ.get('ANDROID_AVD_HOME', str(Path.home()/'.android/avd')))
    config = avds/'test.avd/config.ini'
    config.write_text(configure(config.read_text()))
    # Start once, synchronously, before the logger and boot polling can race.
    subprocess.run([str(adb), 'start-server'], check=True, timeout=30)
    subprocess.run(['bash', 'tools/prepare_emulator_diagnostics.sh'], check=True, timeout=45)
    args = [str(sdk/'emulator/emulator'), '-avd', 'test', '-port', '5554',
            '-no-window', '-gpu', 'swiftshader_indirect', '-feature', '-Vulkan',
            '-accel', 'on', '-noaudio', '-no-boot-anim', '-no-snapshot',
            '-camera-back', 'none', '-camera-front', 'none']
    process = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                               start_new_session=True)
    reader = threading.Thread(target=capture, args=(process.stdout, output/'emulator-output.txt'), daemon=True)
    reader.start()
    try:
        wait_for_boot(process, adb, boot_timeout)
        for setting in ('window_animation_scale', 'transition_animation_scale', 'animator_duration_scale'):
            subprocess.run([str(adb), '-s', 'emulator-5554', 'shell', 'settings', 'put',
                            'global', setting, '0'], check=True, timeout=15)
        return subprocess.run(test_command if test_command is not None else
                              ['bash', 'tools/run_android_runtime.sh'], timeout=1250).returncode
    finally:
        try:
            os.killpg(process.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
            process.wait(timeout=10)
        reader.join(timeout=10)


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--api', required=True, type=int)
    a = p.parse_args()
    raise SystemExit(run(a.api, os.environ['ANDROID_HOME'], 'local-analysis/android-runtime'))
