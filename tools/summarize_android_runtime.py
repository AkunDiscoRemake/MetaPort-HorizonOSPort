# SPDX-License-Identifier: GPL-3.0-only
"""Require actual adapter JUnit cases; Gradle exit zero alone is not runtime proof."""
import argparse
import json
import os
from pathlib import Path
import xml.etree.ElementTree as ET


EXPECTED_CASES=frozenset((
    'sensorsRepeatedStartStopAndClosedGuards',
    'eglNativeLoadRenderPresentShaderCompileAndClose',
    'closingOneOutputDoesNotInvalidateAnother',
    'rendererRejectsDifferentContextAndClosedUse',
    'inputServiceLifecycleRunsOnMainThread'))


SERVICE_CASES=frozenset((
    'absentServiceDoesNotNotifyOrPretendReady',
    'actualBinderReachesSubscriberExactlyOnce',
    'existingProviderNotifiesLateSubscriberAndCannotBeReplaced',
    'unsubscribedRecipientDoesNotReceiveQueuedCallback',
    'blockedMainThreadDoesNotPreventServiceArrival'))
EXPECTED_TESTS=frozenset(
    [('org.metaport.port.AdapterRuntimeTest',n) for n in EXPECTED_CASES]+
    [('org.metaport.port.services.ServiceDirectoryTest',n) for n in SERVICE_CASES])


def summarize(results,api):
    files=sorted(Path(results).rglob('TEST-*.xml'))
    if not 0<len(files)<=32:raise ValueError('Missing/excessive instrumentation XML reports')
    cases=[]
    for path in files:
        if path.stat().st_size>2*1024*1024:raise ValueError('JUnit report size limit')
        tree=ET.parse(path).getroot()
        for case in tree.iter('testcase'):
            cases.append({'class':case.get('classname'),'name':case.get('name'),
                          'failed':case.find('failure') is not None or case.find('error') is not None,
                          'skipped':case.find('skipped') is not None})
        if any(int(s.get('failures','0')) or int(s.get('errors','0')) for s in tree.iter('testsuite')):
            raise ValueError('JUnit suite failure')
    unique={(c['class'],c['name']) for c in cases}
    names={c['name'] for c in cases}
    passed=(unique==EXPECTED_TESTS and len(unique)==len(cases) and
            all(c['name'] and
                not c['failed'] and not c['skipped'] for c in cases))
    return {'api':api,'abi':'x86_64','gpu_configuration':'swiftshader_indirect',
            'tests':cases,'missing_cases':sorted((EXPECTED_CASES|SERVICE_CASES)-names),
            'passed':passed,'original_firmware_executed':False,
            'physical_device_tested':False,'arcore_camera_or_depth_tested':False,
            'quest_hand_inference_tested':False,
            'scope':'Our adapter instrumentation only; test APKs are not METAPORT releases'}

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--results',required=True);p.add_argument('--api',type=int,required=True)
    p.add_argument('--output',required=True);a=p.parse_args()
    try:r=summarize(a.results,a.api)
    except Exception as error:r={'passed':False,'api':a.api,'error':str(error),'original_firmware_executed':False}
    r.update(source_commit=os.environ.get('GITHUB_SHA'),run_id=os.environ.get('GITHUB_RUN_ID'))
    out=Path(a.output);out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(r,indent=2)+'\n')
    raise SystemExit(0 if r['passed'] else 1)
