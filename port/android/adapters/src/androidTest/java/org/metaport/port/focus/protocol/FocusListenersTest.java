// SPDX-License-Identifier: GPL-3.0-only
package org.metaport.port.focus.protocol;

import android.content.ComponentName;
import android.content.Context;
import android.content.Intent;
import android.content.ServiceConnection;
import android.os.Binder;
import android.os.IBinder;
import android.os.Parcel;
import android.os.Process;
import androidx.test.platform.app.InstrumentationRegistry;
import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.LinkedBlockingQueue;
import java.util.concurrent.FutureTask;
import java.util.concurrent.TimeUnit;
import org.junit.Test;
import static org.junit.Assert.*;

public final class FocusListenersTest {
    private static FocusListeners registry() {
        return new FocusListeners((pid,uid,operation)-> {
            assertEquals(Process.myPid(),pid);assertEquals(Process.myUid(),uid);
            assertTrue(operation>=2 && operation<=5);
        });
    }
    private static Binder recorder(List<Integer> received) {
        return new Binder() {
            @Override protected boolean onTransact(int code,Parcel data,Parcel reply,int flags) {
                assertEquals(1,code);assertEquals(FLAG_ONEWAY,flags);
                data.enforceInterface(FocusWire.FOCUS_LISTENER);received.add(data.readInt());
                assertEquals(0,data.dataAvail());return true;
            }
        };
    }
    @Test public void duplicatesTypesAndOwnerWideUnregisterMatchContract() {
        List<Integer> received=new ArrayList<>(); Binder binder=recorder(received);
        try (FocusListeners registry=registry()) {
            assertTrue(registry.registerFocus(binder,1));
            assertTrue(registry.registerFocus(binder,0));assertTrue(registry.registerFocus(binder,0));
            final int[] topCalls={0};
            Binder top=new Binder() {
                @Override protected boolean onTransact(int code,Parcel data,Parcel reply,int flags) {
                    data.enforceInterface(FocusWire.TOP_LISTENER);
                    assertEquals("fixture.top",data.readString());assertEquals(1,data.readInt());
                    int start=data.dataPosition(),size=data.readInt();
                    assertEquals("fixture.app",data.readString());
                    assertEquals(Process.myPid(),data.readInt());assertEquals(Process.myUid(),data.readInt());
                    assertEquals(1,data.readInt());assertEquals(start+size,data.dataPosition());
                    assertEquals(0,data.dataAvail());topCalls[0]++;return true;
                }
            };
            assertTrue(registry.registerTop(top));
            assertEquals(4,registry.size());assertTrue(received.isEmpty());assertEquals(0,topCalls[0]);
            assertEquals(1,registry.notifyTopChanged("fixture.top",new FocusWire.ImmersiveApp("fixture.app",Process.myPid(),Process.myUid(),true)).sent);
            assertEquals(1,topCalls[0]);
            assertEquals(3,registry.notifyFocusChanged().sent);
            assertEquals(java.util.Arrays.asList(0,0,1),received);
            assertTrue(registry.unregisterFocus(0));assertEquals(2,registry.size());
            assertThrows(IllegalArgumentException.class,()->registry.unregisterFocus(0));
            assertTrue(registry.unregisterTop());assertEquals(1,registry.size());
            assertTrue(registry.unregisterFocus(1));assertEquals(0,registry.size());
        }
    }
    @Test public void denialBudgetsInvalidTypesAndCloseDoNotLeakRegistrations() {
        FocusListeners denied=new FocusListeners((p,u,t)->{throw new SecurityException("Test denial");});
        assertThrows(SecurityException.class,()->denied.registerTop(new Binder()));assertEquals(0,denied.size());denied.close();
        FocusListeners registry=registry();
        try {
            assertThrows(IllegalArgumentException.class,()->registry.registerFocus(new Binder(),-1));
            assertThrows(IllegalArgumentException.class,()->registry.registerFocus(new Binder(),2));
            assertThrows(IllegalArgumentException.class,()->registry.unregisterFocus(Integer.MAX_VALUE));
            for (int i=0;i<64;i++) assertTrue(registry.registerTop(new Binder()));
            assertThrows(IllegalStateException.class,()->registry.registerTop(new Binder()));
            assertEquals(64,registry.size());
        } finally {registry.close();}
        assertEquals(0,registry.size());registry.close();
        assertThrows(IllegalStateException.class,()->registry.registerTop(new Binder()));
        assertThrows(IllegalStateException.class,registry::notifyFocusChanged);
    }
    @Test public void callbackReentrancyCancelsLaterEntriesAndIsolatesFailure() {
        List<Integer> received=new ArrayList<>();
        try (FocusListeners registry=registry()) {
            Binder reentrant=new Binder() {
                @Override protected boolean onTransact(int code,Parcel data,Parcel reply,int flags) {
                    data.enforceInterface(FocusWire.FOCUS_LISTENER);received.add(data.readInt());
                    FutureTask<Boolean> remove=new FutureTask<>(()->registry.unregisterFocus(0));
                    Thread thread=new Thread(remove,"FocusUnregisterTest");thread.setDaemon(true);thread.start();
                    try {assertTrue(remove.get(5,TimeUnit.SECONDS));} catch(Exception e){throw new AssertionError(e);}
                    return true;
                }
            };
            Binder broken=new Binder() {
                @Override protected boolean onTransact(int code,Parcel data,Parcel reply,int flags) {throw new IllegalStateException("Test recipient failure");}
            };
            registry.registerFocus(reentrant,0);registry.registerFocus(reentrant,0);
            registry.registerFocus(broken,1);registry.registerFocus(recorder(received),1);
            FocusListeners.Delivery result=registry.notifyFocusChanged();
            assertEquals(2,result.sent);assertEquals(1,result.failed);assertEquals(1,result.skipped);
            assertEquals(java.util.Arrays.asList(0,1),received);
        }
    }
    @Test public void deathDuringLinkCannotActivateStaleEntry() {
        try (FocusListeners registry=registry()) {
            Binder dying=new Binder() {
                @Override public void linkToDeath(IBinder.DeathRecipient recipient,int flags) {recipient.binderDied();}
            };
            assertFalse(registry.registerTop(dying));assertEquals(0,registry.size());
        }
    }
    @Test public void actualRemoteProcessDeathRemovesAllBinderRegistrations() throws Exception {
        Context context=InstrumentationRegistry.getInstrumentation().getTargetContext();
        LinkedBlockingQueue<IBinder> connected=new LinkedBlockingQueue<>();
        ServiceConnection connection=new ServiceConnection() {
            public void onServiceConnected(ComponentName name,IBinder binder){connected.add(binder);}
            public void onServiceDisconnected(ComponentName name){}
        };
        boolean bound=context.bindService(new Intent(context,RemoteListenerService.class),connection,Context.BIND_AUTO_CREATE);
        assertTrue(bound);
        try (FocusListeners registry=registry()) {
            IBinder remote=connected.poll(30,TimeUnit.SECONDS);assertNotNull(remote);
            assertFalse(remote instanceof Binder);
            assertTrue(registry.registerTop(remote));assertTrue(registry.registerTop(remote));
            assertTrue(registry.registerFocus(remote,0));assertTrue(registry.registerFocus(remote,1));
            assertEquals(4,registry.size());
            CountDownLatch death=new CountDownLatch(1);remote.linkToDeath(death::countDown,0);
            Parcel data=Parcel.obtain(),reply=Parcel.obtain();
            try {
                data.writeInterfaceToken("org.metaport.test.RemoteListener");
                assertTrue(remote.transact(42,data,reply,0));reply.readException();
                assertNotEquals(Process.myPid(),reply.readInt());
            } finally {data.recycle();reply.recycle();}
            assertTrue(death.await(20,TimeUnit.SECONDS));
            // Death recipients can run on different Binder pool threads.
            long end=System.nanoTime()+TimeUnit.SECONDS.toNanos(5);
            while (registry.size()!=0 && System.nanoTime()<end) Thread.sleep(10);
            assertEquals(0,registry.size());assertFalse(remote.isBinderAlive());
            assertFalse(registry.registerTop(remote));assertEquals(0,registry.size());
        } finally {context.unbindService(connection);}
    }
}
