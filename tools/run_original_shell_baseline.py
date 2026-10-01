# SPDX-License-Identifier: GPL-3.0-only
"""Enter only from the offline CI network namespace; uses no Meta credentials."""
import os
import argparse
from pathlib import Path
import sys
import subprocess
import signal
from tools.boot_android_emulator import run
from tools.probe_original_shell import offline_guard

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bundled',action='store_true')
    parser.add_argument('--api',type=int,choices=(35,36),default=35);args=parser.parse_args()
    offline_guard()  # Refuse before launching the emulator too.
    root=Path('local-analysis/android-runtime');root.mkdir(parents=True,exist_ok=True)
    command=[sys.executable,'-m','tools.probe_original_shell','--apk',
             'local-analysis/original-cache/VrShell.apk',
             '--output',str(root/'original-shell-baseline.json')]
    if args.bundled:
        command=[sys.executable,'-m','tools.probe_original_shell',
                 '--apk','local-analysis/shell-bundle/signed.apk',
                 '--original','local-analysis/original-cache/VrShell.apk',
                 '--bundle-manifest','local-analysis/shell-bundle/bundle.json',
                 '--instruction-probe-apk','local-analysis/instruction-probe/signed.apk',
                 '--output',str(root/'original-shell-bundled-baseline.json')]
    try:
        code=run(args.api,os.environ['ANDROID_HOME'],root,test_command=command)
    finally:
        pid=root/'boot-logger.pid'
        if pid.exists():
            try:os.kill(int(pid.read_text()),signal.SIGTERM)
            except ProcessLookupError:pass
        subprocess.run([str(Path(os.environ['ANDROID_HOME'])/'platform-tools/adb'),'kill-server'],
                       timeout=15,check=False)
    raise SystemExit(code)
