# SPDX-License-Identifier: GPL-3.0-only
"""Execute isolated native tests under ASan/UBSan and concurrency tests under TSan."""
import argparse
import json
from pathlib import Path
import platform
import subprocess
import time

ROOT=Path(__file__).resolve().parents[1]
HAND=('hand_palette','hand_material','hand_arena_layout','hand_u8_reduce','hand_saturating_pack','hand_fmq_mapping')


def run(output):
    output=Path(output).resolve();output.mkdir(parents=True,exist_ok=True)
    results=[]
    for sanitizer,names in (('address,undefined',('sample_cache','input_router','space_data','focus_session_state','focus_decision','focus_immersive','focus_current','focus_policy_packet','focus_session_binding','focus_window_observation','focus_client_metadata','focus_display_access')+HAND),
                            ('thread',('sample_cache','input_router','focus_session_state','focus_decision','focus_immersive','focus_current','focus_client_metadata','focus_display_access'))):
        for name in names:
            sources=[f'native/tests/{name}_test.cpp']
            if name in HAND:sources=[f'handtracking/tests/native/{name}_test.cpp',f'handtracking/native/src/{name}.cpp']
            elif name in ('focus_immersive','focus_current','focus_policy_packet','focus_session_binding','focus_client_metadata'):sources.append('port/android/adapters/src/main/cpp/focus_immersive.cpp')
            elif name=='space_data':sources.append('port/android/adapters/src/main/cpp/space_data.cpp')
            tag=f'{name}-{sanitizer.replace(",","-")}'
            binary=output/tag
            compile_command=['g++','-std=c++17','-O1','-g','-Wall','-Wextra','-Werror','-UNDEBUG','-pthread',
                             '-fsanitize='+sanitizer,'-fno-omit-frame-pointer','-no-pie',
                             '-Iport/android/adapters/src/main/cpp','-Ihandtracking/native/include',*sources,'-o',str(binary)]
            result={'test':name,'sanitizer':sanitizer,'compile_command':compile_command}
            start=time.monotonic()
            with (output/(tag+'.log')).open('w') as log:
                try:
                    c=subprocess.run(compile_command,cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,timeout=120)
                    result['compile_exit']=c.returncode
                    if c.returncode==0:
                        import os
                        env=dict(os.environ,ASAN_OPTIONS='halt_on_error=1:detect_leaks=1',
                                 UBSAN_OPTIONS='halt_on_error=1:print_stacktrace=1',TSAN_OPTIONS='halt_on_error=1')
                        r=subprocess.run([str(binary)],cwd=ROOT,env=env,stdout=log,stderr=subprocess.STDOUT,timeout=60)
                        result['runtime_exit']=r.returncode
                except subprocess.TimeoutExpired:result['timed_out']=True
            result['passed']=result.get('compile_exit')==0 and result.get('runtime_exit')==0
            result['seconds']=round(time.monotonic()-start,3);results.append(result)
            print(tag,result['passed'],flush=True)
    report={'scope':'Project/adapted helper execution, not an original-library oracle or full hand inference',
            'architecture':platform.machine(),'original_firmware_executed':False,'physical_device_tested':False,
            'tests':results,'passed':all(r['passed'] for r in results)}
    (output/'native-checks.json').write_text(json.dumps(report,indent=2)+'\n')
    return report['passed']

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',default='local-analysis/native-checks')
    raise SystemExit(0 if run(p.parse_args().output) else 1)
