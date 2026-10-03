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
WINDOW_CASES=frozenset(('realWindowFocusTracksStopAndResume','closingStopsObservationAndRejectsRestart'))
FOCUS_WIRE_CASES=frozenset(('allElevenTransactionsUsePinnedFieldOrder',
    'malformedAndDeniedRequestsNeverReachPolicyOperations',
    'callbacksUseOriginalOneWayDescriptorsAndSizedPayload',
    'constructionDoesNotPublishOrInventBackend'))
FOCUS_LISTENER_CASES=frozenset(('duplicatesTypesAndOwnerWideUnregisterMatchContract',
    'denialBudgetsInvalidTypesAndCloseDoNotLeakRegistrations',
    'callbackReentrancyCancelsLaterEntriesAndIsolatesFailure',
    'deathDuringLinkCannotActivateStaleEntry',
    'actualRemoteProcessDeathRemovesAllBinderRegistrations'))
PROCESS_METADATA_CASES=frozenset(('selfMetadataMatchesAndroidIdentityAndPackages',
    'permissionResultsAreReadFromAndroidWithoutFallbackGrants',
    'foreignContextAndMissingPackageMembershipAreRejected'))
NATIVE_FOCUS_CASES=frozenset(('realIdentityReachesNativeCoreAndRefreshPreservesRegistration',
    'nativeBoundaryRejectsForgedIdentityAndStaleTokens',
    'closeAndConcurrentReadsCannotUseFreedNativeState',
    'nativeCapacityIsBoundedAndCloseRestoresCapacity'))
POLICY_EVALUATION_CASES=frozenset(('nativeDecisionsAndLedgerUseBothTypesAndOrdering',
    'nativeImmersiveSelectionAndHistoryRoundTrip',
    'malformedPacketsDoNotMutateEvaluatedState',
    'missingChannelsBudgetsAndUnicodeAreExplicit',
    'concurrentEvaluationAndCloseKeepNativeStateSafe'))
BOOTSTRAP_SESSION_CASES=frozenset(('applicationConstructorHadNativeIdentityBeforeContextAttachment',
    'lateMetadataAttachmentPreservesNativeStateWithoutGrantingFocus',
    'serviceStateCodesPreserveRequiredEffectsIncludingDuplicates',
    'appStateIdentityDenialCannotMutateNativeMembership',
    'appStateCloseAndIndependentCoresDoNotLeakMembership'))
SESSION_BINDING_CASES=frozenset(('sessionRenderingDrivesSelectionWithoutInventingOtherChannels',
    'staleAndForeignSessionObservationsCannotCommit',
    'boundFramesRequireKnownSessionAndCoherentOwnMetadata',
    'sessionRaceCommitsMatchingGenerationOrRejects'))
EXPECTED_TESTS=frozenset(
    [('org.metaport.port.focus.AppProcessMetadataBackendTest',n) for n in PROCESS_METADATA_CASES]+
    [('org.metaport.port.focus.NativeFocusClientTest',n) for n in NATIVE_FOCUS_CASES]+
    [('org.metaport.port.focus.FocusPolicyEvaluationTest',n) for n in POLICY_EVALUATION_CASES]+
    [('org.metaport.port.focus.FocusBootstrapAndSessionTest',n) for n in BOOTSTRAP_SESSION_CASES]+
    [('org.metaport.port.focus.FocusSessionBindingTest',n) for n in SESSION_BINDING_CASES]+
    [('org.metaport.port.AdapterRuntimeTest',n) for n in EXPECTED_CASES]+
    [('org.metaport.port.services.ServiceDirectoryTest',n) for n in SERVICE_CASES]+
    [('org.metaport.port.focus.AppWindowFocusBackendTest',n) for n in WINDOW_CASES]+
    [('org.metaport.port.focus.protocol.VrFocusEndpointTest',n) for n in FOCUS_WIRE_CASES]+
    [('org.metaport.port.focus.protocol.FocusListenersTest',n) for n in FOCUS_LISTENER_CASES])


def summarize(results,api):
    files=sorted(Path(results).rglob('TEST-*.xml'))
    if not 0<len(files)<=32:raise ValueError('Missing/excessive instrumentation XML reports')
    cases=[]
    suite_failed=False
    for path in files:
        if path.stat().st_size>2*1024*1024:raise ValueError('JUnit report size limit')
        tree=ET.parse(path).getroot()
        for case in tree.iter('testcase'):
            failure=case.find('failure')
            if failure is None:failure=case.find('error')
            cases.append({'class':case.get('classname'),'name':case.get('name'),
                          'failed':case.find('failure') is not None or case.find('error') is not None,
                          'skipped':case.find('skipped') is not None,
                          'failure_detail':''.join(failure.itertext())[:8192] if failure is not None else None})
        if any(int(s.get('failures','0')) or int(s.get('errors','0')) for s in tree.iter('testsuite')):
            suite_failed=True
    unique={(c['class'],c['name']) for c in cases}
    names={c['name'] for c in cases}
    passed=(not suite_failed and unique==EXPECTED_TESTS and len(unique)==len(cases) and
            all(c['name'] and
                not c['failed'] and not c['skipped'] for c in cases))
    return {'api':api,'abi':'x86_64','gpu_configuration':'swiftshader_indirect',
            'tests':cases,'suite_failed':suite_failed,'missing_cases':sorted((EXPECTED_CASES|SERVICE_CASES|WINDOW_CASES|FOCUS_WIRE_CASES|FOCUS_LISTENER_CASES|PROCESS_METADATA_CASES|NATIVE_FOCUS_CASES|POLICY_EVALUATION_CASES|BOOTSTRAP_SESSION_CASES|SESSION_BINDING_CASES)-names),
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
