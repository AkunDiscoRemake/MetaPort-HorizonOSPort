// SPDX-License-Identifier: GPL-3.0-only
package org.metaport.port.focus;

import android.content.Context;
import android.os.Process;
import androidx.test.ext.junit.runners.AndroidJUnit4;
import androidx.test.platform.app.InstrumentationRegistry;
import java.lang.reflect.InvocationTargetException;
import java.lang.reflect.Method;
import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.atomic.AtomicReference;
import org.junit.Test;
import org.junit.runner.RunWith;
import static org.junit.Assert.*;

@RunWith(AndroidJUnit4.class)
public class NativeFocusClientTest {
    private Context context() {
        return InstrumentationRegistry.getInstrumentation().getTargetContext();
    }
    private Method method(String name,Class<?>... types) throws Exception {
        Method method=NativeFocusClient.class.getDeclaredMethod(name,types);
        method.setAccessible(true);return method;
    }
    @Test public void realIdentityReachesNativeCoreAndRefreshPreservesRegistration() {
        try (NativeFocusClient client=new NativeFocusClient(context())) {
            for (int i=0;i<5;i++) {
                NativeFocusClient.Registration nativeValue=client.registration();
                AppProcessMetadataBackend.Snapshot observed=client.observeMetadata();
                assertEquals(Process.myPid(),nativeValue.pid);
                assertEquals(Process.myUid(),nativeValue.uid);
                assertEquals(observed.pid,nativeValue.pid);
                assertEquals(observed.uid,nativeValue.uid);
            }
        }
    }
    @Test public void nativeBoundaryRejectsForgedIdentityAndStaleTokens() throws Exception {
        // Reflection only reaches our own private JNI API; not Android hidden APIs.
        Method create=method("nativeCreate",int.class,int.class);
        InvocationTargetException badPid=assertThrows(InvocationTargetException.class,
                ()->create.invoke(null,Process.myPid()+1,Process.myUid()));
        assertTrue(badPid.getCause() instanceof IllegalArgumentException);
        InvocationTargetException badUid=assertThrows(InvocationTargetException.class,
                ()->create.invoke(null,Process.myPid(),Process.myUid()+1));
        assertTrue(badUid.getCause() instanceof IllegalArgumentException);
        Method read=method("nativeIdentity",long.class), destroy=method("nativeDestroy",long.class);
        long token=(Long)create.invoke(null,Process.myPid(),Process.myUid());
        destroy.invoke(null,token);destroy.invoke(null,token);
        long replacement=(Long)create.invoke(null,Process.myPid(),Process.myUid());
        try {
            assertNotEquals(token,replacement);
            for (long invalid:new long[]{0,-1,Long.MAX_VALUE,token}) {
                InvocationTargetException error=assertThrows(InvocationTargetException.class,
                        ()->read.invoke(null,invalid));
                assertTrue(error.getCause() instanceof IllegalStateException);
            }
        } finally { destroy.invoke(null,replacement); }
    }
    @Test public void closeAndConcurrentReadsCannotUseFreedNativeState() throws Exception {
        NativeFocusClient client=new NativeFocusClient(context());
        AtomicReference<Throwable> unexpected=new AtomicReference<>();
        Thread worker=new Thread(()->{
            try {
                for (int i=0;i<100;i++) {
                    try { assertEquals(Process.myPid(),client.registration().pid); }
                    catch (IllegalStateException closed) { return; }
                }
            } catch (Throwable error) { unexpected.set(error); }
        });
        worker.start();client.close();client.close();worker.join(5000);
        assertFalse(worker.isAlive());assertNull(unexpected.get());
        assertThrows(IllegalStateException.class,client::registration);
        assertThrows(IllegalStateException.class,client::observeMetadata);
        try (NativeFocusClient replacement=new NativeFocusClient(context())) {
            assertEquals(Process.myUid(),replacement.registration().uid);
        }
    }
    @Test public void nativeCapacityIsBoundedAndCloseRestoresCapacity() {
        List<NativeFocusClient> clients=new ArrayList<>();
        try {
            for (int i=0;i<32;i++) clients.add(new NativeFocusClient(context()));
            assertThrows(IllegalStateException.class,()->new NativeFocusClient(context()));
            clients.remove(0).close();
            clients.add(new NativeFocusClient(context()));
            assertEquals(Process.myPid(),clients.get(0).registration().pid);
        } finally { for (NativeFocusClient client:clients) client.close(); }
    }
}
