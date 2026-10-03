// SPDX-License-Identifier: GPL-3.0-only
package org.metaport.port.focus.protocol;

import android.os.BadParcelableException;
import android.os.Binder;
import android.os.IBinder;
import android.os.Parcel;
import android.os.Process;
import android.os.RemoteException;
import org.junit.Test;
import static org.junit.Assert.*;
import org.metaport.port.services.ServiceDirectory;
import org.metaport.port.focus.protocol.FocusWire.ClientStatus;
import org.metaport.port.focus.protocol.FocusWire.ImmersiveApp;

/** Deliberate wire fixtures, never an original runtime, focus policy or provider. */
public final class VrFocusEndpointTest {
    private static final ImmersiveApp APP=new ImmersiveApp("fixture.ação",7,9,true);
    private static final class Fixture implements VrFocusEndpoint.Backend {
        int operations, checked; boolean allow=true;
        public void enforceAccess(VrFocusEndpoint.Caller c,int transaction) {
            assertEquals(Process.myPid(),c.pid); assertEquals(Process.myUid(),c.uid);
            checked++;
            if (!allow) throw new SecurityException("Fixture denial");
        }
        private void called(){operations++;}
        public ClientStatus[] getClientFocusStatus(VrFocusEndpoint.Caller c,int type,int[] pids){called();assertEquals(13,type);assertArrayEquals(new int[]{7,8},pids);return new ClientStatus[]{new ClientStatus(7,true),new ClientStatus(8,false)};}
        public boolean registerVrFocusListener(VrFocusEndpoint.Caller c,IBinder b,int type){called();assertNotNull(b);assertEquals(13,type);return true;}
        public boolean unregisterVrFocusListener(VrFocusEndpoint.Caller c,int type){called();assertEquals(13,type);return false;}
        public boolean registerVrTopActivityListener(VrFocusEndpoint.Caller c,IBinder b){called();assertNotNull(b);return true;}
        public boolean unregisterVrTopActivityListener(VrFocusEndpoint.Caller c){called();return false;}
        public void setAppState(VrFocusEndpoint.Caller c,int pid,int state){called();assertEquals(7,pid);assertEquals(2,state);}
        public ImmersiveApp getImmersiveApp(VrFocusEndpoint.Caller c){called();return APP;}
        public String getTopActivity(VrFocusEndpoint.Caller c){called();return "fixture.top";}
        public String[] getForegroundApps(VrFocusEndpoint.Caller c){called();return new String[]{"fixture.a","fixture.b"};}
        public void grantTrackingServiceAccess(VrFocusEndpoint.Caller c,int displayId){called();assertEquals(7,displayId);}
        public void revokeTrackingServiceAccess(VrFocusEndpoint.Caller c,int displayId){called();assertEquals(7,displayId);}
    }
    private static void readApp(Parcel p) {
        assertEquals(1,p.readInt()); int start=p.dataPosition(); int size=p.readInt();
        assertEquals("fixture.ação",p.readString()); assertEquals(7,p.readInt()); assertEquals(9,p.readInt()); assertEquals(1,p.readInt());
        assertEquals(start+size,p.dataPosition());
    }
    @Test public void allElevenTransactionsUsePinnedFieldOrder() throws Exception {
        Fixture backend=new Fixture(); VrFocusEndpoint endpoint=new VrFocusEndpoint(backend);
        for (int code=1;code<=11;code++) {
            Parcel data=Parcel.obtain(), reply=Parcel.obtain();
            try {
                data.writeInterfaceToken("oculus.internal.IVrFocusService");
                switch(code) {
                    case 1: data.writeInt(13); data.writeIntArray(new int[]{7,8}); break;
                    case 2: data.writeStrongBinder(new Binder()); data.writeInt(13); break;
                    case 3: data.writeInt(13); break;
                    case 4: data.writeStrongBinder(new Binder()); break;
                    case 6: data.writeInt(7); data.writeInt(2); break;
                    case 10: case 11: data.writeInt(7); break;
                    default: break;
                }
                assertTrue(endpoint.transact(code,data,reply,0)); reply.readException();
                switch(code) {
                    case 1:
                        assertEquals(2,reply.readInt());
                        for (int i=0;i<2;i++) {assertEquals(1,reply.readInt());assertEquals(12,reply.readInt());assertEquals(7+i,reply.readInt());assertEquals(1-i,reply.readInt());}
                        break;
                    case 2: case 4: assertEquals(1,reply.readInt()); break;
                    case 3: case 5: assertEquals(0,reply.readInt()); break;
                    case 7: readApp(reply); break;
                    case 8: assertEquals("fixture.top",reply.readString()); break;
                    case 9: assertArrayEquals(new String[]{"fixture.a","fixture.b"},reply.createStringArray()); break;
                    default: break;
                }
                assertEquals(0,reply.dataAvail());
            } finally {data.recycle();reply.recycle();}
        }
        assertEquals(11,backend.checked); assertEquals(11,backend.operations);
    }
    @Test public void malformedAndDeniedRequestsNeverReachPolicyOperations() throws Exception {
        Fixture backend=new Fixture(); VrFocusEndpoint endpoint=new VrFocusEndpoint(backend);
        for (int variant=0;variant<6;variant++) {
            Parcel data=Parcel.obtain(), reply=Parcel.obtain();
            try {
                data.writeInterfaceToken(variant==0 ? "wrong.interface" : FocusWire.SERVICE);
                if (variant==1) data.writeInt(123); // Argumentless transaction with trailing data.
                if (variant==2) {data.writeInt(13);data.writeInt(Integer.MAX_VALUE);}
                if (variant==3) data.writeInt(7); // Missing state argument.
                if (variant==4) data.writeStrongBinder(null);
                int code=variant==2 ? 1 : variant==3 ? 6 : variant==4 ? 4 : 5;
                if (variant==5) backend.allow=false;
                try {
                    endpoint.transact(code,data,reply,0); reply.readException();
                    fail("Malformed/denied request accepted");
                } catch (SecurityException | BadParcelableException expected) { /* Must fail closed. */ }
                assertEquals(0,backend.operations);
            } finally {data.recycle();reply.recycle();}
        }
        assertEquals(1,backend.checked); // Only the well-formed, denied call reaches access policy.
    }
    @Test public void callbacksUseOriginalOneWayDescriptorsAndSizedPayload() throws Exception {
        final int[] count={0};
        Binder top=new Binder() {
            @Override protected boolean onTransact(int code,Parcel data,Parcel reply,int flags) {
                assertEquals(1,code);assertEquals(IBinder.FLAG_ONEWAY,flags);assertNull(reply);
                data.enforceInterface("oculus.internal.IVrTopActivityListener");
                assertEquals("fixture.top",data.readString());readApp(data);assertEquals(0,data.dataAvail());count[0]++;return true;
            }
        };
        Binder focus=new Binder() {
            @Override protected boolean onTransact(int code,Parcel data,Parcel reply,int flags) {
                assertEquals(1,code);assertEquals(IBinder.FLAG_ONEWAY,flags);assertNull(reply);
                data.enforceInterface("oculus.internal.IVrFocusListener");assertEquals(13,data.readInt());assertEquals(0,data.dataAvail());count[0]++;return true;
            }
        };
        FocusWire.notifyTopActivity(top,"fixture.top",APP);FocusWire.notifyFocus(focus,13);assertEquals(2,count[0]);
        Binder unsupported=new Binder();
        assertThrows(RemoteException.class,() -> FocusWire.notifyFocus(unsupported,13));
    }
    @Test public void constructionDoesNotPublishOrInventBackend() throws Exception {
        assertThrows(NullPointerException.class,() -> new VrFocusEndpoint(null));
        VrFocusEndpoint endpoint=new VrFocusEndpoint(new Fixture());
        assertNull(ServiceDirectory.checkService("vrfocus"));
        assertNull(endpoint.queryLocalInterface(FocusWire.SERVICE));
        Parcel data=Parcel.obtain(), reply=Parcel.obtain();
        try {
            assertTrue(endpoint.transact(IBinder.INTERFACE_TRANSACTION,data,reply,0));
            assertEquals("oculus.internal.IVrFocusService",reply.readString());
            assertEquals(0,reply.dataAvail());
        } finally {data.recycle();reply.recycle();}
    }
}
