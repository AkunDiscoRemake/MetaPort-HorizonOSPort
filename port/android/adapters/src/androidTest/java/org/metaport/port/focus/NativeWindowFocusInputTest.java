// SPDX-License-Identifier: GPL-3.0-only
package org.metaport.port.focus;

import android.app.Application;
import android.os.Process;
import androidx.lifecycle.Lifecycle;
import androidx.test.core.app.ActivityScenario;
import androidx.test.platform.app.InstrumentationRegistry;
import java.util.concurrent.LinkedBlockingQueue;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicReference;
import org.junit.Test;
import static org.junit.Assert.*;

/** Actual Android windows; all remaining policy channels/metadata are explicit fixtures. */
public final class NativeWindowFocusInputTest {
    private static void main(Runnable task) { InstrumentationRegistry.getInstrumentation().runOnMainSync(task); }
    private static Application app() {
        return (Application)InstrumentationRegistry.getInstrumentation().getTargetContext().getApplicationContext();
    }
    private static void awaitPositive(
            ActivityScenario<FocusTestActivity> scenario,
            LinkedBlockingQueue<NativeFocusClient.WindowSnapshot> events,
            AtomicReference<NativeWindowFocusInput> input) throws Exception {
        long end=System.nanoTime()+TimeUnit.SECONDS.toNanos(20);
        while (System.nanoTime()<end) {
            NativeFocusClient.WindowSnapshot item=events.poll(Math.max(1,end-System.nanoTime()),TimeUnit.NANOSECONDS);
            if (item==null) break;
            if (!item.known) continue;
            AtomicReference<Boolean> focused=new AtomicReference<>(false);
            scenario.onActivity(activity->focused.set(
                    activity.hasWindowFocus() && input.get().snapshot().known));
            if (focused.get()) return;
        }
        throw new AssertionError("No actual positive own-window observation");
    }
    private FocusPolicyFrame frame(int type) {
        FocusPolicyFrame.Client self=new FocusPolicyFrame.Client(Process.myUid(),Process.myPid());
        FocusPolicyFrame.Client[] none=new FocusPolicyFrame.Client[0];
        return FocusPolicyFrame.forObservedInputs(type,1000,
                new FocusPolicyFrame.Request[]{new FocusPolicyFrame.Request(self,0)},none,none,none,none,false,
                new FocusPolicyFrame.Metadata[]{new FocusPolicyFrame.Metadata(self,"fixture","ordinary","fixture")},
                new FocusPolicyFrame.Metadata[0],"other");
    }
    @Test(timeout=120000) public void actualWindowFeedsNativeTypeZeroWithoutInventingSessionOrDisplay() throws Exception {
        try (NativeFocusClient client=NativeFocusClient.createBeforeApplication()) {
            NativeFocusClient.AppStateSnapshot stopped=client.applyAppState(Process.myPid(),2);
            LinkedBlockingQueue<NativeFocusClient.WindowSnapshot> events=new LinkedBlockingQueue<>();
            AtomicReference<NativeWindowFocusInput> input=new AtomicReference<>();
            main(()->{
                input.set(new NativeWindowFocusInput(app(),client,events::add));
                NativeFocusClient.WindowSnapshot unknown=input.get().snapshot();assertFalse(unknown.known);
                assertThrows(IllegalStateException.class,()->client.evaluateWithObservedInputs(frame(0),stopped,unknown));
                input.get().start();
            });
            try (ActivityScenario<FocusTestActivity> scenario=ActivityScenario.launch(FocusTestActivity.class)) {
                awaitPositive(scenario,events,input);
                main(()->{
                    NativeFocusClient.WindowSnapshot window=input.get().snapshot();assertTrue(window.known);
                    NativeFocusClient.ObservedEvaluation result=client.evaluateWithObservedInputs(frame(0),stopped,window);
                    assertEquals(window.generation,result.windowGeneration);
                    assertEquals(stopped.generation,result.sessionGeneration);
                    assertTrue(result.policy.decisions.get(0).focused);assertNull(result.policy.immersive);
                    // Rendering is stopped, other feeds empty; window alone doesn't give type 1 focus.
                    assertFalse(client.evaluateWithObservedInputs(frame(1),stopped,window).policy.decisions.get(0).focused);
                    assertThrows(IllegalArgumentException.class,()->client.evaluate(frame(0)));
                    assertThrows(IllegalArgumentException.class,()->client.evaluateWithSession(frame(0),stopped));
                });
            } finally { main(()->input.get().close()); }
        }
    }
    @Test(timeout=120000) public void windowSourceVersionsAndReplacementRejectOldObservations() throws Exception {
        try (NativeFocusClient client=NativeFocusClient.createBeforeApplication()) {
            NativeFocusClient.AppStateSnapshot session=client.applyAppState(Process.myPid(),2);
            LinkedBlockingQueue<NativeFocusClient.WindowSnapshot> events=new LinkedBlockingQueue<>();
            AtomicReference<NativeWindowFocusInput> input=new AtomicReference<>();
            main(()->{ input.set(new NativeWindowFocusInput(app(),client,events::add));input.get().start(); });
            try (ActivityScenario<FocusTestActivity> scenario=ActivityScenario.launch(FocusTestActivity.class)) {
                awaitPositive(scenario,events,input);
                AtomicReference<NativeFocusClient.WindowSnapshot> old=new AtomicReference<>();
                main(()->{
                    old.set(input.get().snapshot());
                    NativeFocusClient.WindowSnapshot fresh=input.get().snapshot();assertTrue(fresh.known);
                    assertThrows(IllegalStateException.class,()->client.evaluateWithObservedInputs(frame(0),session,old.get()));
                    assertTrue(client.evaluateWithObservedInputs(frame(0),session,fresh).policy.decisions.get(0).focused);
                    assertThrows(IllegalStateException.class,()->new NativeWindowFocusInput(app(),client,s->{}));
                    input.get().close();
                    assertThrows(IllegalStateException.class,()->client.evaluateWithObservedInputs(frame(0),session,fresh));
                    // This is a late observer: an already-started activity is NOT inferred.
                    input.set(new NativeWindowFocusInput(app(),client,events::add));input.get().start();
                    assertFalse(input.get().snapshot().known);
                });
                scenario.moveToState(Lifecycle.State.CREATED);
                assertEquals(Lifecycle.State.CREATED,scenario.getState());
                events.clear();
                scenario.moveToState(Lifecycle.State.RESUMED);
                assertEquals(Lifecycle.State.RESUMED,scenario.getState());
                awaitPositive(scenario,events,input);
                main(()->{
                    NativeFocusClient.WindowSnapshot fresh=input.get().snapshot();assertTrue(fresh.known);
                    assertThrows(IllegalStateException.class,()->client.evaluateWithObservedInputs(frame(0),session,old.get()));
                    assertTrue(client.evaluateWithObservedInputs(frame(0),session,fresh).policy.decisions.get(0).focused);
                });
            } finally { main(()->input.get().close()); }
        }
    }
    @Test(timeout=120000) public void windowRelayEnforcesThreadOwnershipAndSurvivesClientClose() throws Exception {
        NativeFocusClient client=NativeFocusClient.createBeforeApplication();
        AtomicReference<NativeWindowFocusInput> input=new AtomicReference<>();
        LinkedBlockingQueue<NativeFocusClient.WindowSnapshot> events=new LinkedBlockingQueue<>();
        try {
            assertThrows(IllegalStateException.class,()->new NativeWindowFocusInput(app(),client,s->{}));
            main(()->{ input.set(new NativeWindowFocusInput(app(),client,events::add));input.get().start(); });
            assertThrows(IllegalStateException.class,()->input.get().snapshot());
            try (ActivityScenario<FocusTestActivity> scenario=ActivityScenario.launch(FocusTestActivity.class)) {
                awaitPositive(scenario,events,input);client.close();
                scenario.moveToState(Lifecycle.State.CREATED);
                main(()->{
                    assertThrows(IllegalStateException.class,()->input.get().snapshot());
                    input.get().close();input.get().close();
                    assertThrows(IllegalStateException.class,()->input.get().start());
                });
            }
        } finally { if (input.get()!=null) main(()->input.get().close());client.close(); }
    }
}
