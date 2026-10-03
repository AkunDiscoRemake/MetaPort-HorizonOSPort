package org.metaport.port;

import android.content.Context;
import android.hardware.input.InputManager;
import android.os.Handler;
import android.os.Looper;
import android.view.InputDevice;
import android.view.KeyEvent;
import android.view.MotionEvent;
import java.util.Arrays;
import java.util.HashMap;
import java.util.Map;

/** Foreground Android gamepad input. Does NOT enumerate controllers in Horizon yet.
 * Pair through Android settings. No raw HID permissions, root, fabricated poses or IMU integration.
 * All methods and lifecycle callbacks belong on the main thread.
 */
public final class JoyConInput implements AutoCloseable, InputManager.InputDeviceListener {
    static { System.loadLibrary("metaport_adapters"); }
    public static final int A=1, B=2, X=4, Y=8, MENU=16, STICK=32, TRIGGER=64, GRIP=128;
    public enum Mode { HANDS_REQUESTED, JOY_CONS }
    private final InputManager manager;
    private final Handler handler;
    private final Map<Integer,Integer> devices=new HashMap<>();
    private final Map<Integer,Integer> leftBindings=new HashMap<>(), rightBindings=new HashMap<>();
    private long handle;
    private boolean running;

    public JoyConInput(Context context) {
        mainThread();
        manager=context.getApplicationContext().getSystemService(InputManager.class);
        if (manager==null) throw new IllegalStateException("Android input service unavailable");
        handler=new Handler(Looper.getMainLooper());
        handle=nativeCreate();
        if (handle==0) throw new IllegalStateException("Native input allocation failed");
        // Android logical keycodes, not a promise about the printed Nintendo button labels.
        leftBindings.put(KeyEvent.KEYCODE_DPAD_DOWN,X);
        leftBindings.put(KeyEvent.KEYCODE_DPAD_RIGHT,Y);
        leftBindings.put(KeyEvent.KEYCODE_BUTTON_SELECT,MENU);
        leftBindings.put(KeyEvent.KEYCODE_BUTTON_THUMBL,STICK);
        leftBindings.put(KeyEvent.KEYCODE_BUTTON_L2,TRIGGER);
        leftBindings.put(KeyEvent.KEYCODE_BUTTON_L1,GRIP);
        rightBindings.put(KeyEvent.KEYCODE_BUTTON_A,A);
        rightBindings.put(KeyEvent.KEYCODE_BUTTON_B,B);
        rightBindings.put(KeyEvent.KEYCODE_BUTTON_START,MENU);
        rightBindings.put(KeyEvent.KEYCODE_BUTTON_THUMBR,STICK);
        rightBindings.put(KeyEvent.KEYCODE_BUTTON_R2,TRIGGER);
        rightBindings.put(KeyEvent.KEYCODE_BUTTON_R1,GRIP);
    }

    /** Explicit remapping while stopped; one physical key per semantic action per side. */
    public void bind(int side, int keyCode, int action) {
        requireOpen();
        if (running) throw new IllegalStateException("Stop before changing mappings");
        if (side<0 || side>1 || keyCode<=0 || keyCode==KeyEvent.KEYCODE_HOME ||
                keyCode==KeyEvent.KEYCODE_BACK || action<=0 || action>GRIP || (action&(action-1))!=0)
            throw new IllegalArgumentException("Invalid binding");
        Map<Integer,Integer> map=side==0 ? leftBindings : rightBindings;
        map.values().removeIf(value -> value==action);
        map.put(keyCode,action);
    }

    /** Call only while foreground and focused. stop() releases every held action. */
    public void start() {
        requireOpen();
        if (running) return;
        manager.registerInputDeviceListener(this,handler);
        running=true;
        refresh();
    }
    public void stop() {
        requireOpen();
        if (running) manager.unregisterInputDeviceListener(this);
        running=false;devices.clear();nativeReset(handle);
    }
    private void refresh() {
        if (!running) return;
        int[] ids=manager.getInputDeviceIds();Arrays.sort(ids);
        for (int id:ids) {
            if (devices.containsKey(id)) continue;
            InputDevice device=manager.getInputDevice(id);
            if (device==null || device.isVirtual() || !(device.supportsSource(InputDevice.SOURCE_GAMEPAD) ||
                    device.supportsSource(InputDevice.SOURCE_JOYSTICK))) continue;
            int side=JoyConProtocol.side(device.getVendorId(),device.getProductId());
            if (side>=0 && nativeConnect(handle,id,side)) devices.put(id,side);
        }
    }
    @Override public void onInputDeviceAdded(int id) { mainThread();if (running) refresh(); }
    @Override public void onInputDeviceChanged(int id) {
        mainThread();
        if (!running) return;
        nativeDisconnect(handle,id);devices.remove(id);refresh();
    }
    @Override public void onInputDeviceRemoved(int id) {
        mainThread();
        if (!running) return;
        nativeDisconnect(handle,id);devices.remove(id);refresh();
    }

    /** Forward Activity.dispatchKeyEvent. Unrecognized keys/devices remain unconsumed. */
    public boolean onKeyEvent(KeyEvent event) {
        requireOpen();
        Integer side=devices.get(event.getDeviceId());
        if (!running || side==null || (event.getAction()!=KeyEvent.ACTION_DOWN && event.getAction()!=KeyEvent.ACTION_UP)) return false;
        Integer action=(side==0 ? leftBindings : rightBindings).get(event.getKeyCode());
        return action!=null && nativeKey(handle,event.getDeviceId(),action,
                event.getAction()==KeyEvent.ACTION_DOWN && !event.isCanceled(),event.getEventTime()*1_000_000L);
    }
    /** Forward Activity.onGenericMotionEvent. Android Y-down becomes semantic Y-up. */
    public boolean onMotionEvent(MotionEvent event) {
        requireOpen();
        if (!running || !devices.containsKey(event.getDeviceId()) ||
                event.getActionMasked()!=MotionEvent.ACTION_MOVE || !event.isFromSource(InputDevice.SOURCE_JOYSTICK)) return false;
        InputDevice device=event.getDevice();
        if (device==null) return false;
        // Standalone Joy-Cons can expose X/Y or RX/RY. Only accept a complete advertised pair.
        int[][] pairs={{MotionEvent.AXIS_X,MotionEvent.AXIS_Y},{MotionEvent.AXIS_RX,MotionEvent.AXIS_RY},{MotionEvent.AXIS_Z,MotionEvent.AXIS_RZ}};
        for (int[] pair:pairs) {
            InputDevice.MotionRange x=device.getMotionRange(pair[0],event.getSource());
            InputDevice.MotionRange y=device.getMotionRange(pair[1],event.getSource());
            if (x==null || y==null) continue;
            try {
                float nx=JoyConProtocol.normalizeStick(event.getAxisValue(pair[0]),x.getMin(),x.getMax(),x.getFlat());
                float ny=JoyConProtocol.normalizeStick(event.getAxisValue(pair[1]),y.getMin(),y.getMax(),y.getFlat());
                return nativeAxis(handle,event.getDeviceId(),nx,-ny,event.getEventTime()*1_000_000L);
            } catch (IllegalArgumentException invalidRange) { return false; }
        }
        return false;
    }
    /** One frame consumer: drains coalesced edges, including short taps and disconnect releases. */
    public Snapshot snapshot() {
        requireOpen();long[] meta=new long[14];float[] axes=new float[4];
        nativeRead(handle,meta,axes);return new Snapshot(meta,axes,running);
    }
    private static void mainThread() {
        if (Looper.myLooper()!=Looper.getMainLooper()) throw new IllegalStateException("Main thread required");
    }
    private void requireOpen() { mainThread();if(handle==0) throw new IllegalStateException("Closed"); }
    @Override public void close() {
        mainThread();if(handle!=0) { stop();nativeDestroy(handle);handle=0; }
    }
    public static final class Controller {
        public final int androidDeviceId, buttons, pressedSinceRead, releasedSinceRead;
        public final float stickX,stickY;
        public final boolean connected,stickValid;
        public final boolean orientationValid=false,positionValid=false,analogTriggerAvailable=false;
        /** Android uptime clock, NOT elapsedRealtime or Horizon's sensor timebase. */
        public final long lastEventUptimeNs;
        private Controller(long[] m,float[] a,int side) {
            androidDeviceId=(int)m[1+side];connected=androidDeviceId>=0;buttons=(int)m[3+side];
            pressedSinceRead=(int)m[10+side];releasedSinceRead=(int)m[12+side];
            lastEventUptimeNs=m[5+side];stickValid=m[7+side]!=0;
            stickX=a[side*2];stickY=a[side*2+1];
        }
    }
    public static final class Snapshot {
        public final Mode requestedMode;
        public final Controller left,right;
        public final boolean originalHandProviderConnected, foregroundActive;
        public final String horizonBridgeStatus="NOT PORTED YET";
        private Snapshot(long[] m,float[] a,boolean active) {
            foregroundActive=active;
            requestedMode=m[0]==1 ? Mode.JOY_CONS : Mode.HANDS_REQUESTED;
            left=new Controller(m,a,0);right=new Controller(m,a,1);
            originalHandProviderConnected=m[9]!=0;
        }
    }
    private static native long nativeCreate();
    private static native void nativeDestroy(long h);
    private static native boolean nativeConnect(long h,int id,int side);
    private static native void nativeDisconnect(long h,int id);
    private static native void nativeReset(long h);
    private static native boolean nativeKey(long h,int id,int action,boolean down,long time);
    private static native boolean nativeAxis(long h,int id,float x,float y,long time);
    private static native void nativeRead(long h,long[] meta,float[] axes);
}
