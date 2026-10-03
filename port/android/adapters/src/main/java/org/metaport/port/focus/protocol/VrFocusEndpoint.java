// SPDX-License-Identifier: GPL-3.0-only
package org.metaport.port.focus.protocol;

import android.os.BadParcelableException;
import android.os.Binder;
import android.os.IBinder;
import android.os.Parcel;
import android.os.RemoteException;
import java.util.Objects;
import org.metaport.port.focus.protocol.FocusWire.ClientStatus;
import org.metaport.port.focus.protocol.FocusWire.ImmersiveApp;

/** Complete transaction decoder, NOT a focus policy/provider or bootstrap hook.
 * Construction requires every backend operation; no default successful methods.
 * Never published to ServiceDirectory until an actual policy is implemented.
 */
public final class VrFocusEndpoint extends Binder {
    public static final class Caller {
        public final int pid, uid;
        private Caller() { pid=Binder.getCallingPid(); uid=Binder.getCallingUid(); }
    }
    public interface Backend {
        // Must apply the recovered operation-specific permission/identity policy.
        // Throw on denial; caller identity is captured before any async dispatch.
        void enforceAccess(Caller caller, int transaction);
        ClientStatus[] getClientFocusStatus(Caller caller, int type, int[] pids);
        boolean registerVrFocusListener(Caller caller, IBinder listener, int type);
        boolean unregisterVrFocusListener(Caller caller, int type);
        boolean registerVrTopActivityListener(Caller caller, IBinder listener);
        boolean unregisterVrTopActivityListener(Caller caller);
        void setAppState(Caller caller, int pid, int state);
        ImmersiveApp getImmersiveApp(Caller caller);
        String getTopActivity(Caller caller);
        String[] getForegroundApps(Caller caller);
        void grantTrackingServiceAccess(Caller caller, int displayId);
        void revokeTrackingServiceAccess(Caller caller, int displayId);
    }
    private final Backend backend;
    private static final int MAX_CLIENTS=4096;
    public VrFocusEndpoint(Backend backend) {
        this.backend=Objects.requireNonNull(backend);
        attachInterface(null,FocusWire.SERVICE); // Force the original SDK's actual wire path.
    }
    private static void exhausted(Parcel data) {
        if (data.dataAvail()!=0) throw new BadParcelableException("Trailing focus transaction data");
    }
    private static int integer(Parcel data) {
        if (data.dataAvail()<4) throw new BadParcelableException("Truncated focus transaction");
        return data.readInt();
    }
    private static int[] pids(Parcel data) {
        int size=integer(data);
        if (size<0 || size>MAX_CLIENTS || size>data.dataAvail()/4)
            throw new BadParcelableException("Invalid focus PID vector");
        int[] values=new int[size];
        for (int i=0;i<size;i++) values[i]=integer(data);
        return values;
    }
    private static IBinder listener(Parcel data) {
        IBinder listener=data.readStrongBinder();
        if (listener==null) throw new BadParcelableException("Missing focus listener");
        return listener;
    }
    @Override protected boolean onTransact(int code, Parcel data, Parcel reply, int flags) throws RemoteException {
        if (code==INTERFACE_TRANSACTION) { Objects.requireNonNull(reply).writeString(FocusWire.SERVICE); return true; }
        if (code<1 || code>11) return super.onTransact(code,data,reply,flags);
        data.enforceInterface(FocusWire.SERVICE);
        if (reply==null || (flags & FLAG_ONEWAY)!=0) throw new BadParcelableException("Focus requests require a reply");
        Caller caller=new Caller();
        // Decoding and permission checks both precede any stateful operation.
        int first=0, second=0; int[] requested=null; IBinder callback=null;
        switch(code) {
            case 1: first=integer(data); requested=pids(data); break;
            case 2: callback=listener(data); first=integer(data); break;
            case 3: case 10: case 11: first=integer(data); break;
            case 4: callback=listener(data); break;
            case 6: first=integer(data); second=integer(data); break;
            default: break;
        }
        exhausted(data);
        backend.enforceAccess(caller,code);
        switch(code) {
            case 1: {
                ClientStatus[] statuses=Objects.requireNonNull(backend.getClientFocusStatus(caller,first,requested));
                if (statuses.length>MAX_CLIENTS) throw new IllegalStateException("Focus result budget");
                for (ClientStatus status:statuses) Objects.requireNonNull(status);
                reply.writeNoException(); reply.writeInt(statuses.length);
                for (ClientStatus status:statuses) FocusWire.writeClientStatus(reply,status);
                break;
            }
            case 2: { boolean ok=backend.registerVrFocusListener(caller,callback,first); reply.writeNoException(); reply.writeInt(ok?1:0); break; }
            case 3: { boolean ok=backend.unregisterVrFocusListener(caller,first); reply.writeNoException(); reply.writeInt(ok?1:0); break; }
            case 4: { boolean ok=backend.registerVrTopActivityListener(caller,callback); reply.writeNoException(); reply.writeInt(ok?1:0); break; }
            case 5: { boolean ok=backend.unregisterVrTopActivityListener(caller); reply.writeNoException(); reply.writeInt(ok?1:0); break; }
            case 6: backend.setAppState(caller,first,second); reply.writeNoException(); break;
            case 7: {
                ImmersiveApp app=Objects.requireNonNull(backend.getImmersiveApp(caller));
                reply.writeNoException(); FocusWire.writeImmersiveApp(reply,app); break;
            }
            case 8: { String top=backend.getTopActivity(caller); reply.writeNoException(); reply.writeString(top); break; }
            case 9: { String[] apps=Objects.requireNonNull(backend.getForegroundApps(caller));
                if (apps.length>MAX_CLIENTS) throw new IllegalStateException("Foreground result budget");
                reply.writeNoException(); reply.writeStringArray(apps); break; }
            case 10: backend.grantTrackingServiceAccess(caller,first); reply.writeNoException(); break;
            case 11: backend.revokeTrackingServiceAccess(caller,first); reply.writeNoException(); break;
            default: throw new AssertionError("Unreachable focus transaction");
        }
        return true;
    }
}
