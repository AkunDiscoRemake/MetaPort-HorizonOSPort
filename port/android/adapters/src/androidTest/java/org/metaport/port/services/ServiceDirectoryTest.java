// SPDX-License-Identifier: GPL-3.0-only
package org.metaport.port.services;

import android.os.Binder;
import android.os.IBinder;
import androidx.test.platform.app.InstrumentationRegistry;
import org.junit.Test;
import java.util.UUID;
import java.util.concurrent.atomic.AtomicInteger;
import static org.junit.Assert.*;

/** Only test binders are created here; production does not manufacture service providers. */
public final class ServiceDirectoryTest {
    private String name() { return "test." + UUID.randomUUID(); }
    private void drain() { InstrumentationRegistry.getInstrumentation().waitForIdleSync(); }
    @Test public void absentServiceDoesNotNotifyOrPretendReady() {
        String name=name(); AtomicInteger calls=new AtomicInteger();
        ServiceCallback c=new ServiceCallback.Stub() {
            @Override public void onRegistration(String n, IBinder binder) { calls.incrementAndGet(); }
        };
        ServiceDirectory.registerForNotifications(name,c); drain();
        assertNull(ServiceDirectory.checkService(name)); assertEquals(0,calls.get());
        ServiceDirectory.unregisterForNotifications(name,c);
    }
    @Test public void actualBinderReachesSubscriberExactlyOnce() {
        String name=name(); IBinder binder=new Binder(); AtomicInteger calls=new AtomicInteger();
        ServiceCallback c=new ServiceCallback.Stub() {
            @Override public void onRegistration(String n, IBinder received) {
                assertEquals(name,n); assertSame(binder,received); calls.incrementAndGet();
            }
        };
        ServiceDirectory.registerForNotifications(name,c);
        ServiceDirectory.publish(name,binder); ServiceDirectory.publish(name,binder);
        ServiceDirectory.registerForNotifications(name,c); drain();
        assertSame(binder,ServiceDirectory.checkService(name)); assertEquals(1,calls.get());
        ServiceDirectory.unregisterForNotifications(name,c);
    }
    @Test public void existingProviderNotifiesLateSubscriberAndCannotBeReplaced() {
        String name=name(); IBinder binder=new Binder(); AtomicInteger calls=new AtomicInteger();
        ServiceDirectory.publish(name,binder);
        ServiceCallback c=new ServiceCallback.Stub() {
            @Override public void onRegistration(String n, IBinder received) { calls.incrementAndGet(); }
        };
        ServiceDirectory.registerForNotifications(name,c); drain(); assertEquals(1,calls.get());
        try { ServiceDirectory.publish(name,new Binder()); fail("Replaced live provider"); }
        catch (IllegalStateException expected) { assertSame(binder,ServiceDirectory.checkService(name)); }
        ServiceDirectory.unregisterForNotifications(name,c);
    }
    @Test public void unsubscribedRecipientDoesNotReceiveQueuedCallback() {
        String name=name(); AtomicInteger calls=new AtomicInteger();
        ServiceCallback c=new ServiceCallback.Stub() {
            @Override public void onRegistration(String n, IBinder b) { calls.incrementAndGet(); }
        };
        InstrumentationRegistry.getInstrumentation().runOnMainSync(() -> {
            ServiceDirectory.registerForNotifications(name,c);
            ServiceDirectory.publish(name,new Binder());
            ServiceDirectory.unregisterForNotifications(name,c);
        });
        drain(); assertEquals(0,calls.get());
    }
}
