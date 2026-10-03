// SPDX-License-Identifier: GPL-3.0-only
package org.metaport.port.focus;

import android.content.Context;
import android.os.Process;
import androidx.test.ext.junit.runners.AndroidJUnit4;
import androidx.test.platform.app.InstrumentationRegistry;
import java.lang.reflect.Field;
import java.lang.reflect.InvocationTargetException;
import java.lang.reflect.Method;
import java.nio.ByteBuffer;
import java.nio.ByteOrder;
import java.util.Arrays;
import java.util.concurrent.atomic.AtomicReference;
import org.junit.Test;
import org.junit.runner.RunWith;
import static org.junit.Assert.*;

/** Explicit policy fixtures, NOT claimed Android/Quest observations or grants. */
@RunWith(AndroidJUnit4.class)
public class FocusPolicyEvaluationTest {
    private final FocusPolicyFrame.Client self=new FocusPolicyFrame.Client(Process.myUid(),Process.myPid());
    private final FocusPolicyFrame.Client[] none=new FocusPolicyFrame.Client[0];
    private final FocusPolicyFrame.Metadata[] noMetadata=new FocusPolicyFrame.Metadata[0];
    private Context context() { return InstrumentationRegistry.getInstrumentation().getTargetContext(); }
    private FocusPolicyFrame.Request request(FocusPolicyFrame.Client who,int mask) { return new FocusPolicyFrame.Request(who,mask); }
    private FocusPolicyFrame.Metadata metadata(FocusPolicyFrame.Client who,String name,String process) {
        return new FocusPolicyFrame.Metadata(who,name,process,name);
    }
    private FocusPolicyFrame frame(int type,int mask,boolean activity,boolean display,
                                   FocusPolicyFrame.Client window,FocusPolicyFrame.Metadata[] render,
                                   FocusPolicyFrame.Metadata[] live,FocusPolicyFrame.Metadata[] foreground,String top) {
        return new FocusPolicyFrame(type,1234,new FocusPolicyFrame.Request[]{request(self,mask)},
                activity?new FocusPolicyFrame.Client[]{self}:none,none,none,none,window,display,
                render,live,foreground,top);
    }
    @Test public void nativeDecisionsAndLedgerUseBothTypesAndOrdering() {
        try (NativeFocusClient client=new NativeFocusClient(context())) {
            assertThrows(IllegalStateException.class,client::currentFocusMask);
            assertTrue(client.evaluate(frame(0,0,false,false,self,noMetadata,noMetadata,noMetadata,""))
                    .decisions.get(0).focused);
            assertFalse(client.evaluate(frame(1,0,false,false,self,noMetadata,noMetadata,noMetadata,""))
                    .decisions.get(0).focused);
            assertEquals(1,client.currentFocusMask());
            // Keep all four feeds distinct through the transport.
            for (int channel=0;channel<4;channel++) {
                FocusPolicyFrame.Client[] present={self};
                for (int type=0;type<2;type++) {
                    FocusPolicyFrame channels=new FocusPolicyFrame(type,1234,
                            new FocusPolicyFrame.Request[]{request(self,0)},
                            channel==0?present:none,channel==1?present:none,
                            channel==2?present:none,channel==3?present:none,null,false,
                            noMetadata,noMetadata,noMetadata,"");
                    assertEquals(type==0 || channel!=3,client.evaluate(channels).decisions.get(0).focused);
                }
            }
            FocusPolicyFrame.Metadata alert=metadata(self,"fixture","system_server");
            assertFalse(client.evaluate(frame(1,0,true,false,null,new FocusPolicyFrame.Metadata[]{alert},
                    noMetadata,noMetadata,"other")).decisions.get(0).focused);
            assertTrue(client.evaluate(frame(1,2,true,false,null,new FocusPolicyFrame.Metadata[]{alert},
                    noMetadata,noMetadata,"other")).decisions.get(0).focused);
            assertEquals(3,client.currentFocusMask());
            FocusPolicyFrame.Client earlier=new FocusPolicyFrame.Client(-1,55);
            FocusPolicyFrame ordered=new FocusPolicyFrame(1,1234,
                    new FocusPolicyFrame.Request[]{request(self,0),request(self,2),request(earlier,2)},
                    none,none,none,none,null,false,noMetadata,noMetadata,noMetadata,"");
            FocusPolicyResult result=client.evaluate(ordered);
            assertEquals(2,result.decisions.size());assertEquals(-1,result.decisions.get(0).uid);
            assertTrue(result.decisions.get(0).focused);assertFalse(result.decisions.get(1).focused);
            assertEquals(1,result.registeredClientFocusMask);
            assertThrows(UnsupportedOperationException.class,result.decisions::clear);
        }
    }
    @Test public void nativeImmersiveSelectionAndHistoryRoundTrip() {
        try (NativeFocusClient client=new NativeFocusClient(context())) {
            FocusPolicyFrame.Metadata shell=metadata(self,"com.oculus.vrshell","ordinary");
            FocusPolicyFrame.Metadata foreground=metadata(new FocusPolicyFrame.Client(10,222),"top.fixture","ordinary");
            FocusPolicyResult result=client.evaluate(frame(0,0,false,true,null,noMetadata,
                    new FocusPolicyFrame.Metadata[]{shell},new FocusPolicyFrame.Metadata[]{foreground,null},"com.oculus.vrshell"));
            assertEquals("top.fixture",result.topActivity);assertNull(result.immersive);
            result=client.evaluate(frame(1,0,false,true,null,noMetadata,new FocusPolicyFrame.Metadata[]{shell},noMetadata,"com.oculus.vrshell"));
            assertEquals(self.pid,result.immersive.pid);assertTrue(result.immersive.top);
            assertTrue(result.decisions.get(0).focused);assertEquals(1234,result.history.get(0).epochMillis);
            for (int i=0;i<12;i++) {
                FocusPolicyFrame.Metadata alert=metadata(new FocusPolicyFrame.Client(20,10000+i),"alert.fixture","com.oculus.vralertservice");
                result=client.evaluate(frame(1,0,false,true,null,new FocusPolicyFrame.Metadata[]{alert},
                        new FocusPolicyFrame.Metadata[]{shell},noMetadata,"com.oculus.vrshell"));
            }
            assertEquals(10,result.history.size());assertEquals(10011,result.history.get(0).app.pid);
            result=client.evaluate(frame(1,0,false,true,null,noMetadata,noMetadata,noMetadata,""));
            assertNull(result.immersive);assertEquals(10,result.history.size());
            assertThrows(UnsupportedOperationException.class,result.history::clear);
        }
    }
    @Test public void malformedPacketsDoNotMutateEvaluatedState() throws Exception {
        try (NativeFocusClient client=new NativeFocusClient(context())) {
            FocusPolicyFrame valid=frame(0,0,true,true,null,noMetadata,noMetadata,noMetadata,"");
            client.evaluate(valid);assertEquals(1,client.currentFocusMask());
            Method method=NativeFocusClient.class.getDeclaredMethod("nativeEvaluate",long.class,byte[].class);
            method.setAccessible(true);Field handle=NativeFocusClient.class.getDeclaredField("handle");handle.setAccessible(true);
            byte[] bytes=valid.encode();
            for (int length=0;length<bytes.length;length++) reject(method,client,handle,Arrays.copyOf(bytes,length));
            reject(method,client,handle,null);
            reject(method,client,handle,new byte[65537]);
            reject(method,client,handle,Arrays.copyOf(bytes,bytes.length+1));
            for (int offset:new int[]{0,4,16,28}) {
                byte[] changed=bytes.clone();ByteBuffer.wrap(changed).order(ByteOrder.LITTLE_ENDIAN).putInt(offset,-1);
                reject(method,client,handle,changed);
            }
            // Replace the final empty UTF-8 string with an invalid continuation byte.
            byte[] invalid=Arrays.copyOf(bytes,bytes.length+1);
            ByteBuffer.wrap(invalid).order(ByteOrder.LITTLE_ENDIAN).putInt(bytes.length-4,1);
            invalid[bytes.length]=(byte)0x80;reject(method,client,handle,invalid);
            assertEquals(1,client.currentFocusMask());
        }
    }
    private void reject(Method method,NativeFocusClient client,Field handle,byte[] bytes) throws Exception {
        long token=handle.getLong(client);
        InvocationTargetException error=assertThrows(InvocationTargetException.class,()->method.invoke(null,token,bytes));
        assertTrue(error.getCause() instanceof IllegalArgumentException);
        assertEquals(1,client.currentFocusMask());
    }
    @Test public void missingChannelsBudgetsAndUnicodeAreExplicit() {
        assertThrows(NullPointerException.class,()->frame(0,0,false,false,null,null,noMetadata,noMetadata,""));
        assertThrows(IllegalArgumentException.class,()->frame(0,4,false,false,null,noMetadata,noMetadata,noMetadata,""));
        assertThrows(IllegalArgumentException.class,()->frame(2,0,false,false,null,noMetadata,noMetadata,noMetadata,""));
        assertThrows(IllegalArgumentException.class,()->frame(0,0,false,false,null,noMetadata,new FocusPolicyFrame.Metadata[257],noMetadata,""));
        assertThrows(IllegalArgumentException.class,()->frame(0,0,false,false,null,noMetadata,noMetadata,noMetadata,"\ud800"));
        char[] oversized=new char[1025];Arrays.fill(oversized,'a');
        assertThrows(IllegalArgumentException.class,()->frame(0,0,false,false,null,noMetadata,noMetadata,noMetadata,new String(oversized)));
        FocusPolicyFrame.Client[] activities={self};
        FocusPolicyFrame frozen=new FocusPolicyFrame(0,1,new FocusPolicyFrame.Request[]{request(self,0)},
                activities,none,none,none,null,false,noMetadata,noMetadata,noMetadata,"");
        activities[0]=new FocusPolicyFrame.Client(-1,-1);
        try (NativeFocusClient client=new NativeFocusClient(context())) {
            assertTrue(client.evaluate(frozen).decisions.get(0).focused);
            String unicode="ação\u0000\ud83d\ude80";
            FocusPolicyFrame.Metadata rendering=metadata(self,unicode,"ordinary");
            FocusPolicyResult result=client.evaluate(frame(1,0,false,true,null,new FocusPolicyFrame.Metadata[]{rendering},
                    noMetadata,noMetadata,unicode));
            assertEquals(unicode,result.topActivity);assertEquals(unicode,result.immersive.packageName);
        }
        assertThrows(IllegalStateException.class,()->FocusPolicyResult.decode(new byte[0]));
    }
    @Test public void concurrentEvaluationAndCloseKeepNativeStateSafe() throws Exception {
        NativeFocusClient client=new NativeFocusClient(context());
        FocusPolicyFrame frame=frame(0,0,true,true,null,noMetadata,noMetadata,noMetadata,"");
        AtomicReference<Throwable> unexpected=new AtomicReference<>();
        Thread worker=new Thread(()->{
            try { for(int i=0;i<100;i++) {
                try { assertTrue(client.evaluate(frame).decisions.get(0).focused); }
                catch (IllegalStateException closed) { return; }
            }} catch (Throwable error) { unexpected.set(error); }
        });
        worker.start();client.close();worker.join(5000);
        assertFalse(worker.isAlive());assertNull(unexpected.get());
        assertThrows(IllegalStateException.class,()->client.evaluate(frame));
        assertThrows(IllegalStateException.class,client::currentFocusMask);
    }
}
