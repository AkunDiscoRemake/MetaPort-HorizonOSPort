// SPDX-License-Identifier: GPL-3.0-only
package org.metaport.port.focus;

import android.content.Context;
import android.content.ContextWrapper;
import android.content.pm.ApplicationInfo;
import android.os.Process;
import androidx.test.ext.junit.runners.AndroidJUnit4;
import androidx.test.platform.app.InstrumentationRegistry;
import java.lang.reflect.Field;
import java.lang.reflect.InvocationTargetException;
import java.lang.reflect.Method;
import java.util.concurrent.atomic.AtomicReference;
import org.junit.Test;
import org.junit.runner.RunWith;
import static org.junit.Assert.*;

/** Owned fixture APK: service events here are explicit test inputs, not real XR. */
@RunWith(AndroidJUnit4.class)
public class FocusBootstrapAndSessionTest {
    private Context context() { return InstrumentationRegistry.getInstrumentation().getTargetContext(); }
    @Test public void applicationConstructorHadNativeIdentityBeforeContextAttachment() {
        assertNull(FocusBootstrapTestFactory.failure);
        assertTrue(context().getApplicationContext() instanceof FocusBootstrapTestApplication);
        FocusBootstrapTestApplication app=(FocusBootstrapTestApplication)context().getApplicationContext();
        assertTrue(app.contextWasAbsent);assertTrue(app.identityWasNative);assertTrue(app.metadataWasUnavailable);
        assertNull(FocusBootstrapTestFactory.constructingClient); // Test factory releases its own core.
    }
    @Test public void lateMetadataAttachmentPreservesNativeStateWithoutGrantingFocus() {
        try (NativeFocusClient client=NativeFocusClient.createBeforeApplication()) {
            assertEquals(Process.myPid(),client.registration().pid);
            assertThrows(IllegalStateException.class,client::observeMetadata);
            assertFalse(client.appStateSnapshot().known);
            client.applyAppState(Process.myPid(),0);
            client.attachMetadataContext(context());
            assertEquals(Process.myUid(),client.observeMetadata().uid);
            assertEquals(1,client.appStateSnapshot().generation);assertTrue(client.appStateSnapshot().isVisible());
            assertThrows(IllegalStateException.class,client::currentFocusMask);
            Context foreign=new ContextWrapper(context()) {
                @Override public ApplicationInfo getApplicationInfo() {
                    ApplicationInfo info=new ApplicationInfo(super.getApplicationInfo());info.uid=Process.myUid()+1;return info;
                }
            };
            assertThrows(IllegalArgumentException.class,()->client.attachMetadataContext(foreign));
            assertEquals(Process.myUid(),client.observeMetadata().uid);
            assertEquals(1,client.appStateSnapshot().generation);
        }
    }
    @Test public void serviceStateCodesPreserveRequiredEffectsIncludingDuplicates() {
        try (NativeFocusClient client=NativeFocusClient.createBeforeApplication()) {
            NativeFocusClient.AppStateSnapshot unknown=client.applyAppState(Process.myPid(),1);
            assertFalse(unknown.known);assertEquals(0,unknown.generation);
            assertThrows(IllegalStateException.class,unknown::isVisible);noEffects(unknown);
            NativeFocusClient.AppStateSnapshot visible=client.applyAppState(Process.myPid(),0);
            assertTrue(visible.known);assertTrue(visible.isVisible());assertEquals(1,visible.generation);
            assertTrue(visible.membershipChanged);assertFalse(visible.refreshActivityState);
            assertTrue(visible.notifyTopActivity);assertTrue(visible.reportImmersiveUpdate);
            assertEquals(Process.myPid(),visible.pid);assertEquals(Process.myUid(),visible.uid);
            NativeFocusClient.AppStateSnapshot duplicate=client.applyAppState(Process.myPid(),0);
            assertFalse(duplicate.membershipChanged);assertTrue(duplicate.notifyTopActivity);
            assertTrue(duplicate.reportImmersiveUpdate);assertEquals(2,duplicate.generation);
            NativeFocusClient.AppStateSnapshot ignored=client.applyAppState(Process.myPid(),5);
            assertTrue(ignored.isVisible());assertEquals(2,ignored.generation);noEffects(ignored);
            NativeFocusClient.AppStateSnapshot stopped=client.applyAppState(Process.myPid(),2);
            assertFalse(stopped.isVisible());assertEquals(3,stopped.generation);
            assertTrue(stopped.membershipChanged);assertTrue(stopped.refreshActivityState);
            assertTrue(stopped.notifyTopActivity);assertTrue(stopped.reportImmersiveUpdate);
            NativeFocusClient.AppStateSnapshot absent=client.applyAppState(Process.myPid(),2);
            assertFalse(absent.membershipChanged);assertTrue(absent.refreshActivityState);
            assertTrue(absent.notifyTopActivity);assertTrue(absent.reportImmersiveUpdate);assertEquals(4,absent.generation);
            NativeFocusClient.AppStateSnapshot read=client.appStateSnapshot();noEffects(read);
            assertTrue(read.known);assertFalse(read.isVisible());assertEquals(4,read.generation);
            assertThrows(IllegalStateException.class,client::currentFocusMask);
        }
    }
    private void noEffects(NativeFocusClient.AppStateSnapshot value) {
        assertFalse(value.membershipChanged);assertFalse(value.refreshActivityState);
        assertFalse(value.notifyTopActivity);assertFalse(value.reportImmersiveUpdate);
    }
    @Test public void appStateIdentityDenialCannotMutateNativeMembership() throws Exception {
        try (NativeFocusClient client=NativeFocusClient.createBeforeApplication()) {
            client.applyAppState(Process.myPid(),0);
            assertThrows(SecurityException.class,()->client.applyAppState(Process.myPid()+1,2));
            Method method=NativeFocusClient.class.getDeclaredMethod("nativeAppState",long.class,int.class,int.class,int.class,int.class);
            method.setAccessible(true);Field handle=NativeFocusClient.class.getDeclaredField("handle");handle.setAccessible(true);
            long token=handle.getLong(client);
            int pid=Process.myPid(),uid=Process.myUid();
            for (int[] ids:new int[][]{{pid+1,uid,pid},{pid,uid+1,pid},{pid,uid,pid+1}}) {
                InvocationTargetException error=assertThrows(InvocationTargetException.class,
                        ()->method.invoke(null,token,ids[0],ids[1],ids[2],2));
                assertTrue(error.getCause() instanceof SecurityException);
            }
            assertEquals(1,client.appStateSnapshot().generation);assertTrue(client.appStateSnapshot().isVisible());
        }
    }
    @Test public void appStateCloseAndIndependentCoresDoNotLeakMembership() throws Exception {
        NativeFocusClient first=NativeFocusClient.createBeforeApplication();
        try (NativeFocusClient second=NativeFocusClient.createBeforeApplication()) {
            first.applyAppState(Process.myPid(),0);assertFalse(second.appStateSnapshot().known);
            AtomicReference<Throwable> unexpected=new AtomicReference<>();
            Thread worker=new Thread(()->{
                try { for(int i=0;i<100;i++) {
                    try { first.applyAppState(Process.myPid(),i%2==0?0:2); }
                    catch (IllegalStateException closed) { return; }
                }} catch (Throwable error) { unexpected.set(error); }
            });
            worker.start();first.close();worker.join(5000);
            assertFalse(worker.isAlive());assertNull(unexpected.get());
            assertThrows(IllegalStateException.class,first::appStateSnapshot);
            assertThrows(IllegalStateException.class,()->first.applyAppState(Process.myPid(),0));
            assertThrows(IllegalStateException.class,()->first.attachMetadataContext(context()));
            assertFalse(second.appStateSnapshot().known);
        } finally { first.close(); }
        try (NativeFocusClient fresh=NativeFocusClient.createBeforeApplication()) {
            assertFalse(fresh.appStateSnapshot().known);assertEquals(0,fresh.appStateSnapshot().generation);
        }
    }
}
