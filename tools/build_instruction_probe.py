# SPDX-License-Identifier: GPL-3.0-only
"""Build CI-only ARM64 instruction fixture, never a replacement METAPORT app."""
import os
from pathlib import Path
import subprocess
import zipfile


def build(sdk,output,key):
    sdk=Path(sdk);out=Path(output);out.mkdir(parents=True,exist_ok=True)
    src=Path('tests/fixtures/arm64_instructions');bt=sdk/'build-tools/35.0.0'
    jar=sdk/'platforms/android-35/android.jar'
    clang=sdk/'ndk/27.2.12479018/toolchains/llvm/prebuilt/linux-x86_64/bin/aarch64-linux-android29-clang'
    def run(args):subprocess.run([str(a) for a in args],check=True,timeout=120)
    run([clang,'-shared','-fPIC','-O1','-Wall','-Wextra','-Werror','-Wl,--no-undefined',
         '-Wl,-z,max-page-size=16384',src/'probe.c','-o',out/'libinstruction_probe.so'])
    classes=out/'classes';classes.mkdir(exist_ok=True)
    run(['javac','-source','8','-target','8','-classpath',jar,'-d',classes,src/'Probe.java'])
    dex=out/'dex';dex.mkdir(exist_ok=True)
    run([bt/'d8','--lib',jar,'--min-api','29','--output',dex,*sorted(classes.rglob('*.class'))])
    apk=out/'unsigned.apk'
    run([bt/'aapt','package','-f','-M',src/'AndroidManifest.xml','-I',jar,'-F',apk])
    with zipfile.ZipFile(apk,'a') as z:
        z.write(dex/'classes.dex','classes.dex')
        z.write(out/'libinstruction_probe.so','lib/arm64-v8a/libinstruction_probe.so')
    run([bt/'zipalign','-P','16','-f','4',apk,out/'aligned.apk'])
    run([bt/'apksigner','sign','--ks',key,'--ks-key-alias','baseline','--ks-pass','pass:android',
         '--key-pass','pass:android','--out',out/'signed.apk',out/'aligned.apk'])
    run([bt/'apksigner','verify',out/'signed.apk'])

if __name__=='__main__':
    build(os.environ['ANDROID_HOME'],'local-analysis/instruction-probe',Path(os.environ['WORK'])/'test.p12')
