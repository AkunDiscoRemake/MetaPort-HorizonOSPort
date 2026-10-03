// SPDX-License-Identifier: GPL-3.0-only
package org.metaport.port.focus;

import android.content.Context;
import android.content.pm.PackageManager;
import android.os.Process;
import androidx.test.ext.junit.runners.AndroidJUnit4;
import androidx.test.platform.app.InstrumentationRegistry;
import java.util.Arrays;
import java.util.Collections;
import org.junit.Test;
import org.junit.runner.RunWith;
import static org.junit.Assert.*;

/** JNI verification of recovered display tracking access and ClientManager metadata cache. */
@RunWith(AndroidJUnit4.class)
public class FocusDisplayAndMetadataJniTest {
    private static final String GRANT_DISPLAY_PERMISSION =
            "horizonos.permission.GRANT_TRACKING_SERVICE_ACCESS_TO_DISPLAY";

    private Context context() {
        return InstrumentationRegistry.getInstrumentation().getTargetContext();
    }

    @Test public void displayAccessInitialStateMainDisplayToggleAndSecondaryCallbackMasks() {
        try (NativeFocusClient client = NativeFocusClient.createBeforeApplication()) {
            NativeFocusClient.DisplayAccessSnapshot initial = client.displayAccessSnapshot();
            assertEquals(1L, initial.generation);
            assertTrue(initial.mainDisplayFocus);
            assertFalse(initial.trackedDisplaysChanged);
            assertNull(initial.registerDisplayCallbackMask);
            assertArrayEquals(new int[]{0}, initial.activeDisplays);

            // Revoking display 0 clears mainDisplayFocus without removing 0 from activeDisplays.
            NativeFocusClient.DisplayAccessSnapshot revokedMain =
                    client.revokeTrackingServiceAccess(1000, true, 0);
            assertEquals(2L, revokedMain.generation);
            assertFalse(revokedMain.mainDisplayFocus);
            assertFalse(revokedMain.trackedDisplaysChanged);
            assertNull(revokedMain.registerDisplayCallbackMask);
            assertArrayEquals(new int[]{0}, revokedMain.activeDisplays);

            // Granting secondary display 2 transitions size 1 -> 2 and emits callback mask 2.
            NativeFocusClient.DisplayAccessSnapshot grantedD2 =
                    client.grantTrackingServiceAccess(1000, true, 2);
            assertEquals(3L, grantedD2.generation);
            assertFalse(grantedD2.mainDisplayFocus);
            assertTrue(grantedD2.trackedDisplaysChanged);
            assertEquals(Integer.valueOf(2), grantedD2.registerDisplayCallbackMask);
            assertArrayEquals(new int[]{0, 2}, grantedD2.activeDisplays);

            // Duplicate grant on display 2 and third display 5 do not re-emit mask 2.
            NativeFocusClient.DisplayAccessSnapshot dupD2 =
                    client.grantTrackingServiceAccess(1000, true, 2);
            assertFalse(dupD2.trackedDisplaysChanged);
            assertNull(dupD2.registerDisplayCallbackMask);

            NativeFocusClient.DisplayAccessSnapshot grantedD5 =
                    client.grantTrackingServiceAccess(1000, true, 5);
            assertTrue(grantedD5.trackedDisplaysChanged);
            assertNull(grantedD5.registerDisplayCallbackMask);
            assertArrayEquals(new int[]{0, 2, 5}, grantedD5.activeDisplays);

            // DisplayManagerCallback::onDisplayEvent: event != 3 is ignored; display 0 event 3
            // does not alter mainDisplayFocus; secondary display 2 event 3 revokes display 2.
            NativeFocusClient.DisplayAccessSnapshot ReGrantedMain =
                    client.grantTrackingServiceAccess(1041, false, 0);
            assertTrue(ReGrantedMain.mainDisplayFocus);
            long beforeIgnored = ReGrantedMain.generation;
            NativeFocusClient.DisplayAccessSnapshot ignoredEvent = client.onDisplayEvent(2, 1);
            assertEquals(beforeIgnored, ignoredEvent.generation);
            assertArrayEquals(new int[]{0, 2, 5}, ignoredEvent.activeDisplays);

            NativeFocusClient.DisplayAccessSnapshot mainRemovedEvent = client.onDisplayEvent(0, 3);
            assertEquals(beforeIgnored + 1, mainRemovedEvent.generation);
            assertTrue(mainRemovedEvent.mainDisplayFocus);
            assertFalse(mainRemovedEvent.trackedDisplaysChanged);

            NativeFocusClient.DisplayAccessSnapshot d2Removed = client.onDisplayEvent(2, 3);
            assertTrue(d2Removed.trackedDisplaysChanged);
            assertNull(d2Removed.registerDisplayCallbackMask);
            assertArrayEquals(new int[]{0, 5}, d2Removed.activeDisplays);

            // Revoking last secondary display 5 transitions size 2 -> 1 and emits callback mask 0.
            NativeFocusClient.DisplayAccessSnapshot revokedD5 =
                    client.revokeTrackingServiceAccess(1000, true, 5);
            assertTrue(revokedD5.trackedDisplaysChanged);
            assertEquals(Integer.valueOf(0), revokedD5.registerDisplayCallbackMask);
            assertArrayEquals(new int[]{0}, revokedD5.activeDisplays);
        }
    }

    @Test public void displayAccessPermissionGateAllowsAudioServerBypassAndRejectsUnprivilegedCaller() {
        try (NativeFocusClient client = NativeFocusClient.createBeforeApplication()) {
            // Calling UID 0 without PermissionCache grant is denied (2dd78: cbz w0, 2de38).
            assertThrows(SecurityException.class,
                    () -> client.revokeTrackingServiceAccess(0, false, 0));
            assertEquals(1L, client.displayAccessSnapshot().generation);
            assertTrue(client.displayAccessSnapshot().mainDisplayFocus);

            // Real Android permission check on our unprivileged test APK is denied.
            boolean testApkGranted = context().checkPermission(
                    GRANT_DISPLAY_PERMISSION, Process.myPid(), Process.myUid())
                    == PackageManager.PERMISSION_GRANTED;
            assertFalse(testApkGranted);
            assertThrows(SecurityException.class,
                    () -> client.revokeTrackingServiceAccess(Process.myUid(), testApkGranted, 0));
            assertEquals(1L, client.displayAccessSnapshot().generation);

            // Calling UID 1041 (AID_AUDIOSERVER) bypasses PermissionCache even when false.
            NativeFocusClient.DisplayAccessSnapshot audioRevoke =
                    client.revokeTrackingServiceAccess(1041, false, 0);
            assertEquals(2L, audioRevoke.generation);
            assertFalse(audioRevoke.mainDisplayFocus);
        }
    }

    @Test public void clientMetadataBuilderAndPidCacheFollowRecoveredPackageAllowlistAndUidEviction() {
        try (NativeFocusClient client = NativeFocusClient.createBeforeApplication()) {
            // Missing UID returns null and does not populate the cache.
            assertNull(client.buildClientMetadata(
                    700, null, "proc", Collections.singletonList("pkg"), true, true));

            // Multi-package UID with ":sub" matching base package keeps full process name in packageName.
            NativeFocusClient.CachedClientMetadata multi = client.buildClientMetadata(
                    701, 10010, "pkg.two:sub", Arrays.asList("pkg.one", "pkg.two"), false, false);
            assertNotNull(multi);
            assertEquals("pkg.two:sub", multi.packageName);
            assertEquals(0, multi.allowedBackgroundMask);

            // system_server overrides packageName to "android.uid.system:1000".
            NativeFocusClient.CachedClientMetadata sys = client.buildClientMetadata(
                    702, 1000, "system_server", Collections.singletonList("ignored.pkg"), false, false);
            assertEquals("android.uid.system:1000", sys.packageName);

            // Allowlisted package and allowlisted daemon+UID receive mask 3.
            NativeFocusClient.CachedClientMetadata shell = client.buildClientMetadata(
                    703, 10050, "com.oculus.vrshell",
                    Collections.singletonList("com.oculus.vrshell"), false, false);
            assertEquals(3, shell.allowedBackgroundMask);

            NativeFocusClient.CachedClientMetadata daemonOk = client.buildClientMetadata(
                    704, 1041, "/system/bin/audioserver", Collections.emptyList(), false, false);
            assertEquals(3, daemonOk.allowedBackgroundMask);

            NativeFocusClient.CachedClientMetadata daemonWrongUid = client.buildClientMetadata(
                    705, 1000, "/system/bin/audioserver", Collections.emptyList(), false, false);
            assertEquals(0, daemonWrongUid.allowedBackgroundMask);

            // Cache hit via getClientMetadata refreshes returned copy's metadataProcessName
            // without mutating the cached record, and preserves currentFocusMask.
            assertTrue(client.updateCachedCurrentFocus(10010, 701, 0, true));
            assertFalse(client.updateCachedCurrentFocus(99999, 701, 1, true));
            NativeFocusClient.CachedClientMetadata refreshed =
                    client.getClientMetadata(10010, 701, "pkg.two:renamed");
            assertNotNull(refreshed);
            assertEquals("pkg.two:renamed", refreshed.metadataProcessName);
            assertEquals(1, refreshed.currentFocusMask);

            // UID mismatch on getClientMetadata evicts PID 701 from the cache.
            assertNull(client.getClientMetadata(10011, 701, "stale"));
            assertNull(client.getClientMetadata(10010, 701, "after.eviction"));
        }
    }

    @Test public void ownProcessAndroidObservationResolvesWithoutFabricatedAllowlistGrants() {
        try (NativeFocusClient client = new NativeFocusClient(context())) {
            AppProcessMetadataBackend.Snapshot observed = client.observeMetadata();
            NativeFocusClient.CachedClientMetadata resolved = client.buildClientMetadata(
                    observed.pid,
                    observed.uid,
                    observed.androidProcessName,
                    observed.packagesForUid,
                    observed.backgroundHeadPermission == PackageManager.PERMISSION_GRANTED,
                    observed.backgroundInputPermission == PackageManager.PERMISSION_GRANTED);
            assertNotNull(resolved);
            assertEquals(observed.pid, resolved.pid);
            assertEquals(observed.uid, resolved.uid);
            assertEquals(observed.applicationPackage, resolved.packageName);
            assertEquals(0, resolved.allowedBackgroundMask);
            assertEquals(0, resolved.currentFocusMask);
        }
    }
}
