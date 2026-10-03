// SPDX-License-Identifier: GPL-3.0-only
package org.metaport.port.focus;

import android.app.Activity;
import android.app.Application;
import android.os.Bundle;
import android.hardware.display.DisplayManager;
import android.os.Handler;
import android.os.Looper;
import android.os.Process;
import android.view.Display;
import android.view.View;
import android.view.ViewTreeObserver;
import java.util.ArrayList;
import java.util.Collections;
import java.util.Comparator;
import java.util.IdentityHashMap;
import java.util.List;
import java.util.Map;
import java.util.Objects;

/** Actual window observations for this Application only, never global Quest focus.
 * Start before the first activity. Existing activities cannot be enumerated by
 * public Android APIs; this backend reports only activities observed since start.
 * All ownership/lifecycle operations and notifications run on the main thread.
 * This is an input backend, not a vrfocus Binder service or a source of VR poses.
 */
public final class AppWindowFocusBackend implements AutoCloseable, Application.ActivityLifecycleCallbacks, DisplayManager.DisplayListener {
    public interface Listener { void onSnapshot(Snapshot snapshot); }

    public static final class FocusedWindow {
        public final String component;
        public final int displayId;
        public final int pid;
        public final int uid;
        private FocusedWindow(Activity activity, Display display) {
            component = activity.getComponentName().flattenToString();
            displayId = display.getDisplayId();
            pid = Process.myPid();
            uid = Process.myUid();
        }
    }
    public static final class Snapshot {
        public final boolean observing;
        public final int observedStartedActivities;
        public final List<FocusedWindow> focusedWindows;
        private Snapshot(boolean observing, int count, List<FocusedWindow> windows) {
            this.observing = observing;
            observedStartedActivities = count;
            focusedWindows = Collections.unmodifiableList(windows);
        }
    }

    private final Application application;
    private final Map<Activity, Entry> entries = new IdentityHashMap<>();
    private Listener listener;
    private DisplayManager displayManager;
    private boolean started;
    private boolean closed;

    private final class Entry implements ViewTreeObserver.OnWindowFocusChangeListener {
        final Activity activity;
        final View decor;
        final ViewTreeObserver registeredObserver;
        boolean focused;
        Entry(Activity activity) {
            this.activity = activity;
            decor = activity.getWindow().getDecorView();
            focused = decor.hasWindowFocus();
            registeredObserver = decor.getViewTreeObserver();
            registeredObserver.addOnWindowFocusChangeListener(this);
        }
        @Override public void onWindowFocusChanged(boolean hasFocus) {
            mainThread();
            if (!started || entries.get(activity) != this) return;
            focused = hasFocus;
            emit();
        }
        void detach() {
            // Android may merge an unattached view's observer into a new ViewRoot observer.
            ViewTreeObserver current = decor.getViewTreeObserver();
            if (registeredObserver.isAlive()) registeredObserver.removeOnWindowFocusChangeListener(this);
            if (current != registeredObserver && current.isAlive()) current.removeOnWindowFocusChangeListener(this);
        }
    }

    public AppWindowFocusBackend(Application application, Listener listener) {
        this.application = Objects.requireNonNull(application);
        this.listener = Objects.requireNonNull(listener);
    }
    private static void mainThread() {
        if (Looper.myLooper() != Looper.getMainLooper())
            throw new IllegalStateException("Window observations belong to the main thread");
    }
    public void start() {
        mainThread();
        if (closed) throw new IllegalStateException("Window backend closed");
        if (started) return;
        if (application.getApplicationInfo().uid != Process.myUid())
            throw new SecurityException("Foreign application");
        DisplayManager manager = application.getSystemService(DisplayManager.class);
        if (manager == null) throw new IllegalStateException("Display manager unavailable");
        application.registerActivityLifecycleCallbacks(this);
        try { manager.registerDisplayListener(this, new Handler(Looper.getMainLooper())); }
        catch (RuntimeException failure) {
            application.unregisterActivityLifecycleCallbacks(this);
            throw failure;
        }
        displayManager = manager;
        started = true;
        emit();
    }
    public Snapshot snapshot() {
        mainThread();
        List<FocusedWindow> windows = new ArrayList<>();
        if (started) for (Entry entry : entries.values()) {
            Display display = entry.decor.getDisplay();
            if (entry.focused && entry.decor.isAttachedToWindow() && display != null && display.isValid())
                windows.add(new FocusedWindow(entry.activity, display));
        }
        windows.sort(Comparator.comparingInt((FocusedWindow window) -> window.displayId)
            .thenComparing(window -> window.component));
        return new Snapshot(started, entries.size(), windows);
    }
    private void emit() {
        Listener recipient = listener;
        if (recipient != null) recipient.onSnapshot(snapshot());
    }
    private void remove(Activity activity) {
        Entry old = entries.remove(activity);
        if (old != null) { old.detach(); emit(); }
    }
    @Override public void onActivityStarted(Activity activity) {
        mainThread();
        if (!started || activity.getApplication() != application || entries.containsKey(activity)) return;
        entries.put(activity, new Entry(activity));
        emit();
    }
    @Override public void onActivityStopped(Activity activity) { mainThread(); remove(activity); }
    @Override public void onActivityDestroyed(Activity activity) { mainThread(); remove(activity); }
    private void displayChanged() { mainThread(); if (started) emit(); }
    @Override public void onDisplayAdded(int displayId) { displayChanged(); }
    @Override public void onDisplayRemoved(int displayId) { displayChanged(); }
    @Override public void onDisplayChanged(int displayId) { displayChanged(); }
    @Override public void onActivityCreated(Activity activity, Bundle state) {}
    @Override public void onActivityResumed(Activity activity) {}
    @Override public void onActivityPaused(Activity activity) {}
    @Override public void onActivitySaveInstanceState(Activity activity, Bundle state) {}

    @Override public void close() {
        mainThread();
        if (closed) return;
        closed = true;
        if (started) application.unregisterActivityLifecycleCallbacks(this);
        started = false;
        if (displayManager != null) {
            displayManager.unregisterDisplayListener(this);
            displayManager = null;
        }
        for (Entry entry : entries.values()) entry.detach();
        entries.clear();
        try { emit(); } finally { listener = null; }
    }
}
