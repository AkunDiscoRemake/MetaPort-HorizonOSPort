// SPDX-License-Identifier: GPL-3.0-only
package org.metaport.port.focus;

import android.app.Application;
import android.os.Looper;
import java.util.Objects;

/** Own-window evidence relay, not a global observer or complete focus provider.
 * All lifecycle/polling operations run on the main thread. Close this before its
 * client. Empty observations invalidate the channel; they do not mean no focus.
 */
final class NativeWindowFocusInput implements AutoCloseable {
    interface Listener { void onSnapshot(NativeFocusClient.WindowSnapshot snapshot); }
    private final NativeFocusClient client;
    private final AppWindowFocusBackend backend;
    private final long source;
    private final Listener listener;
    private boolean closed;
    private NativeFocusClient.WindowSnapshot latest;
    NativeWindowFocusInput(Application application,NativeFocusClient client,Listener listener) {
        mainThread();this.client=Objects.requireNonNull(client);this.listener=Objects.requireNonNull(listener);
        backend=new AppWindowFocusBackend(application,this::update);
        source=client.attachWindowSource();
    }
    private static void mainThread() {
        if (Looper.myLooper()!=Looper.getMainLooper()) throw new IllegalStateException("Window input belongs to main thread");
    }
    private void requireOpen() { if (closed) throw new IllegalStateException("Window input closed"); }
    private void update(AppWindowFocusBackend.Snapshot snapshot) {
        if (closed) return;
        try { latest=client.observeWindow(source,snapshot); }
        catch (IllegalStateException error) {
            if (client.isClosed()) { close();return; }
            throw error;
        }
        listener.onSnapshot(latest); // Outside native/client locks.
    }
    void start() {
        mainThread();requireOpen();
        try { backend.start(); }
        catch (RuntimeException failure) {
            try { close(); } catch (RuntimeException cleanup) { failure.addSuppressed(cleanup); }
            throw failure;
        }
    }
    NativeFocusClient.WindowSnapshot snapshot() {
        mainThread();requireOpen();update(backend.snapshot());requireOpen();return latest;
    }
    @Override public void close() {
        mainThread();if (closed) return;closed=true;
        try { client.detachWindowSource(source); } finally { backend.close(); }
    }
}
