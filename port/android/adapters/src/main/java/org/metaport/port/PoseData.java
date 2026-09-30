package org.metaport.port;

/** Immutable measured pose in a specified upstream coordinate system; not a Horizon struct. */
public final class PoseData {
    private final float[] position;
    private final float[] rotation;
    public PoseData(float[] positionMeters, float[] quaternionXyzw) {
        if (positionMeters == null || positionMeters.length != 3 || quaternionXyzw == null || quaternionXyzw.length != 4)
            throw new IllegalArgumentException("Expected xyz position and xyzw quaternion");
        position = positionMeters.clone();
        rotation = quaternionXyzw.clone();
        for (float v : position) if (!Float.isFinite(v)) throw new IllegalArgumentException("Nonfinite position");
        double norm2=0;
        for (float v : rotation) {
            if (!Float.isFinite(v)) throw new IllegalArgumentException("Nonfinite quaternion");
            norm2+=(double)v*v;
        }
        if (norm2 < 1e-12) throw new IllegalArgumentException("Zero quaternion");
        double inv=1.0/Math.sqrt(norm2);
        for (int i=0;i<4;i++) rotation[i]=(float)(rotation[i]*inv);
    }
    public float[] positionMeters() { return position.clone(); }
    public float[] quaternionXyzw() { return rotation.clone(); }
}
