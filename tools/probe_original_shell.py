# SPDX-License-Identifier: GPL-3.0-only
"""Offline install/start baseline of UNMODIFIED VrShell, not a METAPORT release.

Must run inside a network namespace with loopback as its only interface. Never
requests credentials, grants permissions, patches signatures, or fakes services.
"""
import argparse
import hashlib
import json
import os
import re
from pathlib import Path
import subprocess
import tempfile
import time
from horizon.ui.prepare_shell import POLICY

PACKAGE='com.oculus.vrshell'
COMPONENT=PACKAGE+'/com.oculus.vrshell.HomeActivity'


def offline_guard():
    interfaces=json.loads(subprocess.check_output(['ip','-j','link','show'],text=True,timeout=10))
    if not interfaces or any(i.get('ifname')!='lo' for i in interfaces):
        raise RuntimeError('Refusing original APK execution outside loopback-only network namespace')


def adb_command(adb, arguments, timeout=30):
    # File backing bounds memory even if the guest returns very large output.
    with tempfile.TemporaryFile() as stream:
        try:
            proc=subprocess.run([str(adb),'-s','emulator-5554',*arguments],
                                stdout=stream,stderr=subprocess.STDOUT,timeout=timeout)
            code=proc.returncode
        except subprocess.TimeoutExpired:
            code=124
        stream.seek(0);raw=stream.read(65537)
    return {'exit_code':code,'text':raw[:65536].decode(errors='replace'),
            'truncated':len(raw)>65536}


def package_uid(text):
    matches=re.findall(r'^package:'+re.escape(PACKAGE)+r' uid:(\d+)$',text,re.MULTILINE)
    if len(matches)!=1:return None
    value=int(matches[0])
    return value if 10000<=value<=2147483647 else None


def inspect(apk, adb, observe_seconds=20, original=None, bundle_manifest=None):
    if not 0<=observe_seconds<=30:raise ValueError('Observation budget')
    apk=Path(apk);policy=json.loads(POLICY.read_text())
    if not 0<apk.stat().st_size<=512*1024*1024:raise ValueError('APK bounds')
    digest=hashlib.sha256()
    with apk.open('rb') as stream:
        for block in iter(lambda:stream.read(1024*1024),b''):digest.update(block)
    sha=digest.hexdigest()
    bundled=original is not None or bundle_manifest is not None
    bundle=None
    if bundled:
        if original is None or bundle_manifest is None:raise ValueError('Incomplete bundle provenance')
        from horizon.ui.bundle_shell_dependencies import compare_apks
        from handtracking.ai.inspect_original import digest
        manifest=Path(bundle_manifest)
        if manifest.stat().st_size>2*1024*1024:raise ValueError('Bundle evidence budget')
        bundle=json.loads(manifest.read_text())
        if digest(Path(original))!=policy['apk_sha256'] or bundle['source_apk_sha256']!=policy['apk_sha256']:
            raise ValueError('Unverified original source')
        if sha!=bundle['signed_apk_sha256']:raise ValueError('Unverified signed bundle')
        compare_apks(original,apk,bundle['added_members'])
    elif sha!=policy['apk_sha256']:raise ValueError('Unverified original APK')
    offline_guard()
    report={'apk_sha256':sha,'original_apk_unmodified':not bundled,
            'source_apk_sha256':policy['apk_sha256'],'original_members_unchanged':True,
            'instruction_adaptations':bundle.get('instruction_adaptations',[]) if bundle else [],
            'bundled_library_count':len(bundle['added_members']) if bundle else 0,'network_isolated':True,
            'installation_attempted':False,'installation_succeeded':False,
            'activity_start_attempted':False,'port_ready':False,
            'physical_device_tested':False,'original_ui_rendering_validated':False,
            'hand_inference_validated':False,'remote_meta_servers_contacted':False,
            'scope':'Original APK offline baseline; process survival does not establish a working port'}
    call=lambda args,timeout=30:adb_command(adb,args,timeout)
    abi=call(['shell','getprop','ro.product.cpu.abilist'])
    report['guest_api']=call(['shell','getprop','ro.build.version.sdk'])
    report['guest_abi']=abi;report['native_bridge']=call(['shell','getprop','ro.dalvik.vm.native.bridge'])
    if abi['exit_code']!=0 or 'arm64-v8a' not in abi['text'].strip().split(','):
        report['result']='UNSUPPORTED_OR_UNKNOWN_GUEST_ABI';return report
    report['installation_attempted']=True
    install=call(['install','--no-streaming',str(apk)],180);report['install']=install
    if install['exit_code']!=0 or 'Success' not in install['text'].splitlines():
        report['result']='INSTALL_REJECTED';return report
    report['installation_succeeded']=True
    identity=call(['shell','cmd','package','list','packages','--user','0','-U',PACKAGE])
    uid=package_uid(identity['text']) if identity['exit_code']==0 else None
    report['application_uid']=uid
    call(['shell','am','force-stop',PACKAGE]);call(['logcat','-b','crash','-c'])
    try:
        report['activity_start_attempted']=True
        report['start']=call(['shell','am','start','-W','-n',COMPONENT],60)
        time.sleep(observe_seconds)
        report['process_after_observation']=call(['shell','pidof',PACKAGE])
        report['crash_buffer']=call(['logcat','-b','crash','-d','-v','threadtime'])
        if uid is not None:
            report['application_log']=call(['logcat','-b','main','-b','system','-d',
                                            '--uid='+str(uid),'-t','400','-v','threadtime'])
        report['activity_state']=call(['shell','dumpsys','activity','top'])
        report['observation_seconds']=observe_seconds
        crash=report['crash_buffer']
        report['application_crash_recorded']=crash['exit_code']==0 and (
            '>>> '+PACKAGE+' <<<' in crash['text'] or
            'Process: '+PACKAGE+', PID:' in crash['text'])
        report['result']=('APPLICATION_CRASH_RECORDED' if report['application_crash_recorded']
                          else 'START_ATTEMPT_RECORDED_NOT_VALIDATED')
    finally:
        call(['shell','am','force-stop',PACKAGE])
    return report


PREFLIGHT_REQUIRED=('control','lse','acquire','acquire32','acquire64')


def run_experiment(apk,adb,original=None,bundle_manifest=None,instruction_probe_apk=None):
    preflight=None
    if instruction_probe_apk:
        from tools.probe_arm64_instructions import inspect as probe_instructions
        preflight=probe_instructions(instruction_probe_apk,adb)
        cases=preflight.get('cases',{})
        missing=[name for name in PREFLIGHT_REQUIRED
                 if cases.get(name,{}).get('expected_value_observed') is not True]
        if missing:
            return {'result':'INSTRUCTION_PREFLIGHT_NOT_PASSED','instruction_probe':preflight,
                    'failed_or_missing_preflight_cases':missing,'installation_attempted':False,
                    'port_ready':False,'original_ui_rendering_validated':False}
    report=inspect(apk,adb,original=original,bundle_manifest=bundle_manifest)
    if preflight is not None:
        report['instruction_probe']=preflight
        report['instruction_preflight_passed']=True
    return report


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--apk',required=True);p.add_argument('--output',required=True)
    p.add_argument('--original');p.add_argument('--bundle-manifest')
    p.add_argument('--instruction-probe-apk')
    a=p.parse_args()
    try:r=run_experiment(a.apk,Path(os.environ['ANDROID_HOME'])/'platform-tools/adb',
                        original=a.original,bundle_manifest=a.bundle_manifest,
                        instruction_probe_apk=a.instruction_probe_apk)
    except Exception as error:r={'result':'EXPERIMENT_FAILED','error':str(error),'port_ready':False}
    r.update(source_commit=os.environ.get('GITHUB_SHA'),run_id=os.environ.get('GITHUB_RUN_ID'))
    output=Path(a.output);output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps(r,indent=2)+'\n')
    raise SystemExit(1 if r['result']=='EXPERIMENT_FAILED' else 0)
