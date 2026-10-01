# SPDX-License-Identifier: GPL-3.0-only
"""Independent control/LSE/RCpc executions in the offline emulator only."""
from tools.probe_original_shell import adb_command,offline_guard

PACKAGE='org.metaport.internal.cpuprobe'


def inspect(apk,adb):
    offline_guard()
    call=lambda args,timeout=30:adb_command(adb,args,timeout)
    report={'scope':'CI instruction fixture, not Horizon UI or physical hardware validation',
            'port_ready':False,'cases':{}}
    installed=call(['install','--no-streaming',str(apk)],120);report['install']=installed
    if installed['exit_code'] or 'Success' not in installed['text'].splitlines():return report
    try:
        for mode in ('control','lse','rcpc','acquire','rcpc64','acquire64','rcpc32','acquire32'):
            call(['shell','am','force-stop',PACKAGE]);call(['logcat','-b','crash','-c'])
            result=call(['shell','am','instrument','-w','-e','mode',mode,PACKAGE+'/.Probe'],60)
            report['cases'][mode]={'instrumentation':result,
                'expected_value_observed': result['exit_code']==0 and
                    'INSTRUMENTATION_RESULT: value=7' in result['text'].splitlines() and
                    'INSTRUMENTATION_CODE: -1' in result['text'].splitlines(),
                'crash':call(['logcat','-b','crash','-d','-v','threadtime'])}
    finally:
        call(['shell','am','force-stop',PACKAGE]);call(['uninstall',PACKAGE])
    return report
