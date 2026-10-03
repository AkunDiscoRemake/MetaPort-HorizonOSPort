// SPDX-License-Identifier: GPL-3.0-only
package org.metaport.port.focus;

import android.os.Process;
import androidx.test.ext.junit.runners.AndroidJUnit4;
import java.lang.reflect.Field;
import java.lang.reflect.Method;
import java.lang.reflect.InvocationTargetException;
import java.util.concurrent.atomic.AtomicReference;
import org.junit.Test;
import org.junit.runner.RunWith;
import static org.junit.Assert.*;

/** Native session coupling with explicit metadata/other-channel fixtures, not Horizon execution. */
@RunWith(AndroidJUnit4.class)
public class FocusSessionBindingTest {
    private final FocusPolicyFrame.Client own=new FocusPolicyFrame.Client(Process.myUid(),Process.myPid());
    private final FocusPolicyFrame.Client[] empty=new FocusPolicyFrame.Client[0];
    private final FocusPolicyFrame.Metadata meta=new FocusPolicyFrame.Metadata(own,"fixture","ordinary","fixture");
    private FocusPolicyFrame frame(int type,boolean display,FocusPolicyFrame.Client window,String top) {
        return FocusPolicyFrame.forSession(type,1000,new FocusPolicyFrame.Request[]{new FocusPolicyFrame.Request(own,0)},
                empty,empty,empty,empty,window,display,new FocusPolicyFrame.Metadata[]{meta},
                new FocusPolicyFrame.Metadata[0],top);
    }
    @Test public void sessionRenderingDrivesSelectionWithoutInventingOtherChannels() {
        try (NativeFocusClient client=NativeFocusClient.createBeforeApplication()) {
            NativeFocusClient.AppStateSnapshot visible=client.applyAppState(own.pid,0);
            NativeFocusClient.SessionEvaluation value=client.evaluateWithSession(frame(1,true,null,"fixture"),visible);
            assertEquals(visible.generation,value.sessionGeneration);
            assertEquals(own.pid,value.policy.immersive.pid);assertTrue(value.policy.decisions.get(0).focused);
            assertFalse(client.evaluateWithSession(frame(1,false,null,"fixture"),visible).policy.decisions.get(0).focused);
            assertNull(client.evaluateWithSession(frame(1,true,null,"other"),visible).policy.immersive);
            NativeFocusClient.AppStateSnapshot stopped=client.applyAppState(own.pid,2);
            FocusPolicyResult result=client.evaluateWithSession(frame(1,true,null,"fixture"),stopped).policy;
            assertNull(result.immersive);assertFalse(result.decisions.get(0).focused);
            FocusPolicyFrame.Metadata shell=new FocusPolicyFrame.Metadata(own,"com.oculus.vrshell","ordinary","com.oculus.vrshell");
            FocusPolicyFrame shellFrame=FocusPolicyFrame.forSession(1,1000,
                    new FocusPolicyFrame.Request[]{new FocusPolicyFrame.Request(own,0)},empty,empty,empty,empty,
                    null,true,new FocusPolicyFrame.Metadata[]{shell},new FocusPolicyFrame.Metadata[0],"com.oculus.vrshell");
            // Preserve the original shell fallback; stopped rendering alone doesn't
            // mandate clearing the selected immersive app or its focus.
            assertEquals(own.pid,client.evaluateWithSession(shellFrame,stopped).policy.immersive.pid);
            // A separate observed window still feeds type 0 even when rendering stopped.
            assertTrue(client.evaluateWithSession(frame(0,false,own,"fixture"),stopped).policy.decisions.get(0).focused);
        }
    }
    @Test public void staleAndForeignSessionObservationsCannotCommit() throws Exception {
        try (NativeFocusClient client=NativeFocusClient.createBeforeApplication();
             NativeFocusClient other=NativeFocusClient.createBeforeApplication()) {
            FocusPolicyFrame frame=frame(1,true,null,"fixture");
            NativeFocusClient.AppStateSnapshot first=client.applyAppState(own.pid,0);
            client.evaluateWithSession(frame,first);assertEquals(2,client.currentFocusMask());
            NativeFocusClient.AppStateSnapshot foreign=other.applyAppState(own.pid,0);
            assertEquals(first.generation,foreign.generation);
            assertThrows(IllegalArgumentException.class,()->client.evaluateWithSession(frame,foreign));
            client.applyAppState(own.pid,0); // Duplicate still advances generation.
            assertThrows(IllegalStateException.class,()->client.evaluateWithSession(frame,first));
            assertEquals(2,client.currentFocusMask()); // Last evaluation unchanged, not a fresh grant.
            NativeFocusClient.AppStateSnapshot current=client.appStateSnapshot();
            client.applyAppState(own.pid,7); // Unrecognized code doesn't alter this channel.
            assertTrue(client.evaluateWithSession(frame,current).policy.decisions.get(0).focused);
            client.applyAppState(own.pid,2);
            assertThrows(IllegalStateException.class,()->client.evaluateWithSession(frame,current));
            assertFalse(client.evaluateWithSession(frame,client.appStateSnapshot()).policy.decisions.get(0).focused);
            Field handle=NativeFocusClient.class.getDeclaredField("handle");handle.setAccessible(true);
            Method method=NativeFocusClient.class.getDeclaredMethod("nativeEvaluateSession",long.class,long.class,long.class,byte[].class);
            method.setAccessible(true);
            long token=handle.getLong(client),foreignToken=handle.getLong(other);
            InvocationTargetException denied=assertThrows(InvocationTargetException.class,
                    ()->method.invoke(null,token,foreignToken,client.appStateSnapshot().generation,frame.encode()));
            assertTrue(denied.getCause() instanceof IllegalArgumentException);
        }
    }
    @Test public void boundFramesRequireKnownSessionAndCoherentOwnMetadata() {
        try (NativeFocusClient client=NativeFocusClient.createBeforeApplication()) {
            FocusPolicyFrame frame=frame(1,true,null,"fixture");
            NativeFocusClient.AppStateSnapshot unknown=client.appStateSnapshot();
            assertThrows(IllegalStateException.class,()->client.evaluateWithSession(frame,unknown));
            assertThrows(IllegalArgumentException.class,()->client.evaluate(frame)); // No fallback to empty rendering.
            NativeFocusClient.AppStateSnapshot observed=client.applyAppState(own.pid,0);
            FocusPolicyFrame explicit=new FocusPolicyFrame(1,1000,new FocusPolicyFrame.Request[0],empty,empty,empty,empty,
                    null,true,new FocusPolicyFrame.Metadata[0],new FocusPolicyFrame.Metadata[]{meta},new FocusPolicyFrame.Metadata[0],"fixture");
            assertThrows(IllegalArgumentException.class,()->client.evaluateWithSession(explicit,observed));
            for (FocusPolicyFrame.Metadata[] live:new FocusPolicyFrame.Metadata[][]{
                    {},{meta,meta},{new FocusPolicyFrame.Metadata(new FocusPolicyFrame.Client(own.uid,own.pid+1),"fixture","ordinary","fixture")}}) {
                FocusPolicyFrame invalid=FocusPolicyFrame.forSession(1,1000,new FocusPolicyFrame.Request[0],empty,empty,empty,empty,
                        null,true,live,new FocusPolicyFrame.Metadata[0],"fixture");
                assertThrows(IllegalArgumentException.class,()->client.evaluateWithSession(invalid,observed));
            }
            FocusPolicyFrame mismatch=FocusPolicyFrame.forSession(1,1000,new FocusPolicyFrame.Request[0],empty,empty,empty,empty,
                    null,true,new FocusPolicyFrame.Metadata[]{meta},
                    new FocusPolicyFrame.Metadata[]{new FocusPolicyFrame.Metadata(own,"different","ordinary","fixture")},"fixture");
            assertThrows(IllegalArgumentException.class,()->client.evaluateWithSession(mismatch,observed));
            assertThrows(IllegalStateException.class,client::currentFocusMask);
        }
    }
    @Test public void sessionRaceCommitsMatchingGenerationOrRejects() throws Exception {
        try (NativeFocusClient client=NativeFocusClient.createBeforeApplication()) {
            client.applyAppState(own.pid,0);
            Field handle=NativeFocusClient.class.getDeclaredField("handle");handle.setAccessible(true);
            long token=handle.getLong(client);
            Method update=NativeFocusClient.class.getDeclaredMethod("nativeAppState",long.class,int.class,int.class,int.class,int.class);
            update.setAccessible(true);
            AtomicReference<Throwable> failure=new AtomicReference<>();
            // Bypass the Java monitor intentionally to exercise native exclusion.
            Thread updater=new Thread(()->{
                try { for(int i=0;i<500;i++) update.invoke(null,token,own.pid,own.uid,own.pid,i%2==0?0:2); }
                catch (Throwable error) { failure.set(error); }
            });
            updater.start();
            try {
                for(int i=0;i<200;i++) {
                    NativeFocusClient.AppStateSnapshot observed=client.appStateSnapshot();
                    try {
                        NativeFocusClient.SessionEvaluation result=client.evaluateWithSession(frame(1,true,null,"fixture"),observed);
                        assertEquals(observed.generation,result.sessionGeneration);
                        assertEquals(observed.isVisible(),result.policy.decisions.get(0).focused);
                    } catch (IllegalStateException stale) {
                        assertEquals("Stale or unavailable session observation",stale.getMessage());
                    }
                }
            } finally { updater.join(10000); }
            assertFalse(updater.isAlive());assertNull(failure.get());
            NativeFocusClient.AppStateSnapshot latest=client.appStateSnapshot();
            assertEquals(latest.isVisible(),client.evaluateWithSession(frame(1,true,null,"fixture"),latest).policy.decisions.get(0).focused);
        }
    }
}
