package org.metaport.port;

/** Hardware identification and normalization only; not Nintendo HID or a Quest ABI. */
public final class JoyConProtocol {
    private JoyConProtocol() { }
    public static final int LEFT=0, RIGHT=1, UNKNOWN=-1;
    public static int side(int vendorId, int productId) {
        if (vendorId != 0x057e) return UNKNOWN;
        if (productId == 0x2006) return LEFT;
        if (productId == 0x2007) return RIGHT;
        return UNKNOWN; // Pro Controller, Switch 2 and name-only matches are not assumed compatible.
    }
    /** Per-axis deadzone; Android device units in, centered [-1,1] out. */
    public static float normalizeStick(float value, float min, float max, float flat) {
        if (!Float.isFinite(value) || !Float.isFinite(min) || !Float.isFinite(max) ||
                !Float.isFinite(flat) || min>=max || flat<0)
            throw new IllegalArgumentException("Invalid axis calibration");
        double radius=((double)max-min)*0.5;
        if (flat>=radius) throw new IllegalArgumentException("Deadzone covers axis range");
        double center=((double)min+max)*0.5;
        double v=Math.max(-1,Math.min(1,(value-center)/radius));
        double dead=flat/radius;
        if (Math.abs(v)<=dead) return 0;
        return (float)Math.copySign((Math.abs(v)-dead)/(1-dead),v);
    }
}
