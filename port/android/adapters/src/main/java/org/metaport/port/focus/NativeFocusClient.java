// SPDX-License-Identifier: GPL-3.0-only
package org.metaport.port.focus;

import android.content.Context;

/** Own-process identity registration in the native policy core, not a focus service.
 * Does NOT publish Binder or turn raw permission observations into
 * grants. Metadata normalization and coherent decision inputs remain separate work.
 * Close explicitly. Each instance owns an independent core, not a global provider.
 */
public final class NativeFocusClient implements AutoCloseable {
    static { System.loadLibrary("metaport_adapters"); }
    private final AppProcessMetadataBackend backend;
    private long handle;

    public static final class Registration {
        public final int pid;
        public final int uid;
        private Registration(int pid, int uid) { this.pid=pid; this.uid=uid; }
    }
    public NativeFocusClient(Context context) {
        backend=new AppProcessMetadataBackend(context);
        AppProcessMetadataBackend.Snapshot observed=backend.snapshot();
        // Only identity is forwarded. Raw permission results are NOT grants.
        handle=nativeCreate(observed.pid,observed.uid);
        if (handle==0) throw new IllegalStateException("Native focus registration failed");
    }
    public synchronized Registration registration() {
        requireOpen();
        int[] identity=nativeIdentity(handle);
        return new Registration(identity[0],identity[1]);
    }
    /** Refresh metadata without reinstalling the native record/clearing its state. */
    public synchronized AppProcessMetadataBackend.Snapshot observeMetadata() {
        requireOpen();
        AppProcessMetadataBackend.Snapshot observed=backend.snapshot();
        int[] identity=nativeIdentity(handle);
        if (observed.pid!=identity[0] || observed.uid!=identity[1])
            throw new IllegalStateException("Process identity changed");
        return observed;
    }
    // Internal bridge only: no production observer assembles this complete frame yet.
    synchronized FocusPolicyResult evaluate(FocusPolicyFrame frame) {
        requireOpen();
        return FocusPolicyResult.decode(nativeEvaluate(handle,java.util.Objects.requireNonNull(frame).encode()));
    }
    // Diagnostic bookkeeping only. Check result.registeredClientEvaluatedTypes before
    // interpreting a clear bit: a type never queried for this client is still unknown.
    synchronized int currentFocusMask() { requireOpen();return nativeCurrentFocusMask(handle); }
    private void requireOpen() {
        if (handle==0) throw new IllegalStateException("Closed native focus client");
    }
    @Override public synchronized void close() {
        if (handle!=0) { nativeDestroy(handle); handle=0; }
    }
    private static native byte[] nativeEvaluate(long handle,byte[] packet);
    private static native int nativeCurrentFocusMask(long handle);
    private static native long nativeCreate(int pid, int uid);
    private static native int[] nativeIdentity(long handle);
    private static native void nativeDestroy(long handle);
}
