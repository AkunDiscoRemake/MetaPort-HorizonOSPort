// SPDX-License-Identifier: GPL-3.0-only
package org.metaport.port.focus;

import android.app.Application;
import android.os.Process;
import androidx.lifecycle.Lifecycle;
import androidx.test.core.app.ActivityScenario;
import androidx.test.platform.app.InstrumentationRegistry;
import org.junit.Test;
import java.util.concurrent.LinkedBlockingQueue;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicInteger;
import java.util.function.Predicate;
import static org.junit.Assert.*;

public final class AppWindowFocusBackendTest {
    private static void main(Runnable task) {
        InstrumentationRegistry.getInstrumentation().runOnMainSync(task);
    }
    private static AppWindowFocusBackend.Snapshot await(
            LinkedBlockingQueue<AppWindowFocusBackend.Snapshot> events,
            Predicate<AppWindowFocusBackend.Snapshot> condition) throws Exception {
        long end = System.nanoTime() + TimeUnit.SECONDS.toNanos(20);
        while (System.nanoTime() < end) {
            AppWindowFocusBackend.Snapshot snapshot = events.poll(Math.max(1,end-System.nanoTime()),TimeUnit.NANOSECONDS);
            if (snapshot == null) break;
            if (condition.test(snapshot)) return snapshot;
        }
        throw new AssertionError("No matching actual window observation");
    }
    private static AppWindowFocusBackend backend(AppWindowFocusBackend.Listener listener) {
        Application application=(Application)InstrumentationRegistry.getInstrumentation().getTargetContext().getApplicationContext();
        return new AppWindowFocusBackend(application,listener);
    }
    @Test(timeout=120000) public void realWindowFocusTracksStopAndResume() throws Exception {
        LinkedBlockingQueue<AppWindowFocusBackend.Snapshot> events = new LinkedBlockingQueue<>();
        AppWindowFocusBackend backend = backend(events::add);
        main(backend::start);
        try (ActivityScenario<FocusTestActivity> scenario=ActivityScenario.launch(FocusTestActivity.class)) {
            AppWindowFocusBackend.Snapshot first=await(events,s -> !s.focusedWindows.isEmpty());
            assertTrue(first.observing);
            AppWindowFocusBackend.FocusedWindow window=first.focusedWindows.get(0);
            assertEquals(Process.myPid(),window.pid); assertEquals(Process.myUid(),window.uid);
            assertTrue(window.displayId>=0); assertTrue(window.component.endsWith("FocusTestActivity"));
            assertThrows(UnsupportedOperationException.class,() -> first.focusedWindows.clear());
            events.clear();
            scenario.moveToState(Lifecycle.State.CREATED);
            await(events,s -> s.observing && s.observedStartedActivities==0 && s.focusedWindows.isEmpty());
            events.clear();
            scenario.moveToState(Lifecycle.State.RESUMED);
            await(events,s -> s.observing && !s.focusedWindows.isEmpty());
        } finally { main(backend::close); }
    }
    @Test(timeout=120000) public void closingStopsObservationAndRejectsRestart() throws Exception {
        LinkedBlockingQueue<AppWindowFocusBackend.Snapshot> events=new LinkedBlockingQueue<>();
        AtomicInteger count=new AtomicInteger();
        AppWindowFocusBackend backend=backend(s -> { count.incrementAndGet(); events.add(s); });
        assertThrows(IllegalStateException.class,backend::start);
        main(backend::start);
        try (ActivityScenario<FocusTestActivity> scenario=ActivityScenario.launch(FocusTestActivity.class)) {
            await(events,s -> !s.focusedWindows.isEmpty());
            main(backend::close);
            AppWindowFocusBackend.Snapshot closed=await(events,s -> !s.observing);
            assertEquals(0,closed.observedStartedActivities); assertTrue(closed.focusedWindows.isEmpty());
            int stoppedCount=count.get();
            scenario.moveToState(Lifecycle.State.CREATED); scenario.moveToState(Lifecycle.State.RESUMED);
            main(() -> {
                assertFalse(backend.snapshot().observing);
                assertThrows(IllegalStateException.class,backend::start);
                backend.close();
            });
            assertEquals(stoppedCount,count.get());
        } finally { main(backend::close); }
    }
}
