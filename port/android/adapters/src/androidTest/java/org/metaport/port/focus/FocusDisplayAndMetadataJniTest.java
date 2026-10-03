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

            // Evaluating policy updates ClientManager cached current_focus (0x25460 -> 0x12bc0/0x12de0).
            FocusPolicyFrame.Client self = new FocusPolicyFrame.Client(observed.uid, observed.pid);
            FocusPolicyFrame.Metadata meta = new FocusPolicyFrame.Metadata(
                    self, resolved.packageName, resolved.metadataProcessName, resolved.packageName);
            FocusPolicyFrame grantedFrame = new FocusPolicyFrame(
                    0, 1000L,
                    new FocusPolicyFrame.Request[]{new FocusPolicyFrame.Request(self, resolved.allowedBackgroundMask)},
                    new FocusPolicyFrame.Client[]{self},
                    new FocusPolicyFrame.Client[0],
                    new FocusPolicyFrame.Client[]{self},
                    new FocusPolicyFrame.Client[]{self},
                    self, true,
                    new FocusPolicyFrame.Metadata[]{meta},
                    new FocusPolicyFrame.Metadata[]{meta},
                    new FocusPolicyFrame.Metadata[]{meta},
                    resolved.packageName);
            assertTrue(client.evaluate(grantedFrame).decisions.get(0).focused);
            assertEquals(1, client.getClientMetadata(
                    observed.uid, observed.pid, observed.androidProcessName).currentFocusMask);
        }

        // End-to-end VrFocusService (0x29210..0x2dd60) wire & policy verification.
        try (VrFocusService service = VrFocusService.createBeforeApplication((perm, pid, uid) -> true)) {
            service.attachMetadataContext(context());
            final java.util.List<String> topEvents = new java.util.ArrayList<>();
            final java.util.List<Integer> focusEvents = new java.util.ArrayList<>();
            android.os.Binder topListener = new android.os.Binder() {
                @Override protected boolean onTransact(int code, android.os.Parcel data, android.os.Parcel reply, int flags) {
                    data.enforceInterface("oculus.internal.IVrTopActivityListener");
                    String top = data.readString();
                    assertEquals(1, data.readInt());
                    data.readInt(); // parcelable size
                    String pkg = data.readString();
                    int pid = data.readInt();
                    int uid = data.readInt();
                    int isTop = data.readInt();
                    topEvents.add(top + "|" + pkg + ":" + pid + ":" + uid + ":" + isTop);
                    return true;
                }
            };
            android.os.Binder focusListener = new android.os.Binder() {
                @Override protected boolean onTransact(int code, android.os.Parcel data, android.os.Parcel reply, int flags) {
                    data.enforceInterface("oculus.internal.IVrFocusListener");
                    focusEvents.add(data.readInt());
                    return true;
                }
            };
            android.os.Parcel data = android.os.Parcel.obtain(), reply = android.os.Parcel.obtain();
            try {
                // Register top activity listener (code 4) and focus listener (code 2).
                data.writeInterfaceToken("oculus.internal.IVrFocusService");
                data.writeStrongBinder(topListener);
                assertTrue(service.endpoint().transact(4, data, reply, 0));
                reply.readException();
                assertEquals(1, reply.readInt());
                data.setDataPosition(0); data.setDataSize(0); reply.setDataPosition(0); reply.setDataSize(0);

                data.writeInterfaceToken("oculus.internal.IVrFocusService");
                data.writeStrongBinder(focusListener);
                data.writeInt(0);
                assertTrue(service.endpoint().transact(2, data, reply, 0));
                reply.readException();
                assertEquals(1, reply.readInt());
                assertTrue(topEvents.isEmpty());
                assertTrue(focusEvents.isEmpty());

                // Initial getImmersiveApp (code 7) throws NullPointerException (-4 EX_NULL_POINTER, 0x2c660).
                data.setDataPosition(0); data.setDataSize(0); reply.setDataPosition(0); reply.setDataSize(0);
                data.writeInterfaceToken("oculus.internal.IVrFocusService");
                assertTrue(service.endpoint().transact(7, data, reply, 0));
                assertThrows(NullPointerException.class, reply::readException);

                // setAppState(myPid, 2) (code 6, 0x2c450) notifies top listener with default ImmersiveApp("",0,0,false) (0x2a7e0).
                data.setDataPosition(0); data.setDataSize(0); reply.setDataPosition(0); reply.setDataSize(0);
                data.writeInterfaceToken("oculus.internal.IVrFocusService");
                data.writeInt(Process.myPid());
                data.writeInt(2);
                assertTrue(service.endpoint().transact(6, data, reply, 0));
                reply.readException();
                assertTrue(service.isSessionRendering());
                assertEquals(Collections.singletonList("|:0:0:0"), topEvents);

                // Evaluating own process as active com.oculus.vrshell grants HEAD focus and updates ImmersiveApp.
                assertTrue(service.evaluateOwnProcess(
                        0, 2000L, "com.oculus.vrshell", "com.oculus.vrshell",
                        false, false, true, false, true, true, true));
                assertEquals(Collections.singletonList(0), focusEvents);
                assertEquals("com.oculus.vrshell|com.oculus.vrshell:" + Process.myPid() + ":" + Process.myUid() + ":1",
                        topEvents.get(topEvents.size() - 1));
            } catch (android.os.RemoteException e) {
                throw new AssertionError(e);
            } finally {
                data.recycle();
                reply.recycle();
            }
        }
    }
}
