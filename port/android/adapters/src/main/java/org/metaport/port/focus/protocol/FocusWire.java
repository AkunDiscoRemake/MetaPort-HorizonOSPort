// SPDX-License-Identifier: GPL-3.0-only
package org.metaport.port.focus.protocol;

import android.os.IBinder;
import android.os.Parcel;
import android.os.RemoteException;
import java.util.Objects;

/** Owned wire encoding reconstructed from pinned Java smali and native AIDL.
 * Values must be supplied by a real policy; no window-to-XR inference here.
 * Not classes in oculus.internal: never shadows the bundled original SDK.
 */
public final class FocusWire {
    public static final String NAME = "vrfocus";
    public static final String SERVICE = "oculus.internal.IVrFocusService";
    public static final String TOP_LISTENER = "oculus.internal.IVrTopActivityListener";
    public static final String FOCUS_LISTENER = "oculus.internal.IVrFocusListener";
    private FocusWire() {}

    public static final class ClientStatus {
        public final int pid;
        public final boolean hasFocus;
        public ClientStatus(int pid, boolean hasFocus) { this.pid=pid; this.hasFocus=hasFocus; }
    }
    public static final class ImmersiveApp {
        public final String packageName;
        public final int pid, uid;
        public final boolean isTopActivity;
        public ImmersiveApp(String packageName, int pid, int uid, boolean isTopActivity) {
            this.packageName=packageName; this.pid=pid; this.uid=uid; this.isTopActivity=isTopActivity;
        }
    }
    private static void finishObject(Parcel parcel, int start) {
        int end=parcel.dataPosition();
        parcel.setDataPosition(start); parcel.writeInt(end-start); parcel.setDataPosition(end);
    }
    static void writeClientStatus(Parcel parcel, ClientStatus status) {
        Objects.requireNonNull(status);
        parcel.writeInt(1); // Typed-object presence, outside the sized payload.
        int start=parcel.dataPosition(); parcel.writeInt(0);
        parcel.writeInt(status.pid); parcel.writeInt(status.hasFocus ? 1 : 0);
        finishObject(parcel,start);
    }
    static void writeImmersiveApp(Parcel parcel, ImmersiveApp app) {
        Objects.requireNonNull(app);
        parcel.writeInt(1);
        int start=parcel.dataPosition(); parcel.writeInt(0);
        parcel.writeString(app.packageName); parcel.writeInt(app.pid); parcel.writeInt(app.uid);
        parcel.writeInt(app.isTopActivity ? 1 : 0);
        finishObject(parcel,start);
    }
    public static void notifyTopActivity(IBinder listener, String topActivity, ImmersiveApp app) throws RemoteException {
        Objects.requireNonNull(listener); Objects.requireNonNull(app);
        Parcel data=Parcel.obtain();
        try {
            data.writeInterfaceToken(TOP_LISTENER); data.writeString(topActivity); writeImmersiveApp(data,app);
            if (!listener.transact(1,data,null,IBinder.FLAG_ONEWAY)) throw new RemoteException("Top-activity callback unsupported");
        } finally { data.recycle(); }
    }
    public static void notifyFocus(IBinder listener, int focusType) throws RemoteException {
        Objects.requireNonNull(listener);
        Parcel data=Parcel.obtain();
        try {
            data.writeInterfaceToken(FOCUS_LISTENER); data.writeInt(focusType);
            if (!listener.transact(1,data,null,IBinder.FLAG_ONEWAY)) throw new RemoteException("Focus callback unsupported");
        } finally { data.recycle(); }
    }
}
