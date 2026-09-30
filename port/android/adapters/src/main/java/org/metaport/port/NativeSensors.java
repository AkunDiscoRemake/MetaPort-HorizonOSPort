package org.metaport.port;

import android.content.Context;
import android.os.SystemClock;

/** Real NDK sensor producer. No Horizon memory-broker ABI or synthetic 6DOF. */
public final class NativeSensors implements AutoCloseable {
    static { System.loadLibrary("metaport_adapters"); }
    public static final int ROTATION = 1, GYROSCOPE = 2, ACCELERATION = 4;
    private long handle;
    private int availableMask;

    public NativeSensors(Context context) {
        handle = nativeCreate(context.getOpPackageName());
        if (handle == 0) throw new IllegalStateException("Native sensor allocation failed");
    }

    /** 10ms = 100Hz default; no high-sampling permission required. Call on foreground. */
    public synchronized int start(int periodUs) {
        requireOpen();
        if (periodUs < 10000 || periodUs > 1000000)
            throw new IllegalArgumentException("Sampling period must be 10000..1000000 us");
        int result = nativeStart(handle, periodUs);
        if (result < 0) throw new IllegalStateException("Sensor queue initialization failed: " + result);
        availableMask = result;
        return result; // Only sensors successfully enabled on the actual device.
    }

    /** Call on pause; no background tracking or wake lock. */
    public synchronized void stop() {
        requireOpen();
        nativeStop(handle);
        availableMask = 0;
    }

    public synchronized Snapshot snapshot(long maxAgeNs) {
        requireOpen();
        if (maxAgeNs < 0 || maxAgeNs > 1_000_000_000L)
            throw new IllegalArgumentException("Freshness limit must be <= 1 second");
        long[] metadata = new long[9];
        float[] values = new float[12];
        nativeRead(handle, SystemClock.elapsedRealtimeNanos(), maxAgeNs, metadata, values);
        return new Snapshot(availableMask, metadata, values);
    }

    private void requireOpen() { if (handle == 0) throw new IllegalStateException("Closed"); }
    @Override public synchronized void close() {
        if (handle != 0) { nativeDestroy(handle); handle = 0; availableMask = 0; }
    }

    public static final class Snapshot {
        /** Coordinates remain Android natural-device sensor axes, NOT XR world axes. */
        public final int enabledSensors;
        public final boolean orientationValid, gyroscopeValid, accelerationValid;
        public final long orientationTimeNs, gyroscopeTimeNs, accelerationTimeNs;
        public final int orientationAccuracy, gyroscopeAccuracy, accelerationAccuracy;
        /** xyzw quaternion from GAME_ROTATION_VECTOR; no absolute north or position. */
        public final float[] orientation;
        public final float[] angularVelocityRadPerSec;
        /** Includes gravity, in m/s². It is NOT integrated into fabricated position. */
        public final float[] accelerationMetersPerSecSquared;
        private Snapshot(int mask, long[] m, float[] v) {
            enabledSensors = mask;
            orientationTimeNs=m[0]; gyroscopeTimeNs=m[3]; accelerationTimeNs=m[6];
            orientationAccuracy=(int)m[1]; gyroscopeAccuracy=(int)m[4]; accelerationAccuracy=(int)m[7];
            orientationValid=m[2]!=0; gyroscopeValid=m[5]!=0; accelerationValid=m[8]!=0;
            orientation=orientationValid ? new float[]{v[0],v[1],v[2],v[3]} : null;
            angularVelocityRadPerSec=gyroscopeValid ? new float[]{v[4],v[5],v[6]} : null;
            accelerationMetersPerSecSquared=accelerationValid ? new float[]{v[8],v[9],v[10]} : null;
        }
    }
    private static native long nativeCreate(String packageName);
    private static native int nativeStart(long handle, int periodUs);
    private static native void nativeStop(long handle);
    private static native void nativeRead(long handle, long nowNs, long maxAgeNs, long[] metadata, float[] values);
    private static native void nativeDestroy(long handle);
}
