package org.metaport.port;

import android.view.Surface;

/** Android window output for a future original compositor bridge; NOT a compositor.
 * Owns a context on the creating render thread; shares display lifetime with other
 * EglOutput instances. Do not mix with external EGL display owners (including
 * ARCore-managed contexts) without an explicit display-ownership contract. No stereo/distortion/layers are synthesized.
 */
public final class EglOutput implements AutoCloseable {
    static { System.loadLibrary("metaport_adapters"); }
    private final Thread owner = Thread.currentThread();
    private long handle;
    public EglOutput(Surface surface) {
        if (surface == null || !surface.isValid()) throw new IllegalArgumentException("Invalid surface");
        handle = nativeCreate(surface);
        if (handle == 0) throw new IllegalStateException("EGL output creation failed");
    }
    private void check() {
        if (Thread.currentThread() != owner) throw new IllegalStateException("Use the owning render thread");
        if (handle == 0) throw new IllegalStateException("Closed");
    }
    public void makeCurrent() { check(); nativeMakeCurrent(handle); }
    public int[] surfaceSize() { check(); return nativeSize(handle); }
    public int glesMajorVersion() { check(); return nativeVersion(handle); }
    public boolean supportsPresentationTimestamp() { check(); return nativePresentationSupported(handle); }
    /** Optional timestamp is in CLOCK_MONOTONIC ns, NOT sensor BOOTTIME or ARCore time.
     * Zero omits the timestamp. Unsupported explicit timestamps throw, never silently vanish.
     */
    public void present(long presentationTimeNs) {
        check();
        if (presentationTimeNs < 0) throw new IllegalArgumentException("Negative timestamp");
        nativePresent(handle, presentationTimeNs);
    }
    @Override public void close() {
        if (Thread.currentThread() != owner) throw new IllegalStateException("Use the owning render thread");
        if (handle != 0) { nativeDestroy(handle); handle = 0; }
    }
    private static native long nativeCreate(Surface surface);
    private static native void nativeMakeCurrent(long handle);
    private static native int[] nativeSize(long handle);
    private static native int nativeVersion(long handle);
    private static native boolean nativePresentationSupported(long handle);
    private static native void nativePresent(long handle, long timestampNs);
    private static native void nativeDestroy(long handle);
}
