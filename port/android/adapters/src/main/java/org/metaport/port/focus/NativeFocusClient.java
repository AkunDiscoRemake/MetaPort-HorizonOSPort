// SPDX-License-Identifier: GPL-3.0-only
package org.metaport.port.focus;

import android.content.Context;
import android.os.Binder;
import android.os.Process;

/** Own-process identity registration in the native policy core, not a focus service.
 * Does NOT publish Binder or turn raw permission observations into
 * grants. Metadata normalization and coherent decision inputs remain separate work.
 * Close explicitly. Each instance owns an independent core, not a global provider.
 */
public final class NativeFocusClient implements AutoCloseable {
    static { System.loadLibrary("metaport_adapters"); }
    private AppProcessMetadataBackend backend;
    private long handle;

    public static final class Registration {
        public final int pid;
        public final int uid;
        private Registration(int pid, int uid) { this.pid=pid; this.uid=uid; }
    }
    public NativeFocusClient(Context context) {
        backend=new AppProcessMetadataBackend(context);
        AppProcessMetadataBackend.Snapshot observed=backend.snapshot();
        // Only identity is forwarded. Raw permission results are NOT grants.
        handle=nativeCreate(observed.pid,observed.uid);
        if (handle==0) throw new IllegalStateException("Native focus registration failed");
    }
    private NativeFocusClient() {
        // Public OS identity APIs work before Application is constructed/attached.
        // No package name, metadata, permission or focus is inferred here.
        handle=nativeCreate(Process.myPid(),Process.myUid());
        if (handle==0) throw new IllegalStateException("Native focus registration failed");
    }
    public static NativeFocusClient createBeforeApplication() { return new NativeFocusClient(); }
    public synchronized void attachMetadataContext(Context context) {
        requireOpen();
        AppProcessMetadataBackend candidate=new AppProcessMetadataBackend(context);
        AppProcessMetadataBackend.Snapshot observed=candidate.snapshot();
        int[] identity=nativeIdentity(handle);
        if (observed.pid!=identity[0] || observed.uid!=identity[1])
            throw new IllegalStateException("Process identity changed");
        backend=candidate; // No native reinstall, no clearing of previous state.
    }
    public synchronized Registration registration() {
        requireOpen();
        int[] identity=nativeIdentity(handle);
        return new Registration(identity[0],identity[1]);
    }
    /** Refresh metadata without reinstalling the native record/clearing its state. */
    public synchronized AppProcessMetadataBackend.Snapshot observeMetadata() {
        requireOpen();
        if (backend==null) throw new IllegalStateException("Metadata context not attached");
        AppProcessMetadataBackend.Snapshot observed=backend.snapshot();
        int[] identity=nativeIdentity(handle);
        if (observed.pid!=identity[0] || observed.uid!=identity[1])
            throw new IllegalStateException("Process identity changed");
        return observed;
    }
    // Internal bridge only: no production observer assembles this complete frame yet.
    synchronized FocusPolicyResult evaluate(FocusPolicyFrame frame) {
        requireOpen();
        return FocusPolicyResult.decode(nativeEvaluate(handle,java.util.Objects.requireNonNull(frame).encode()));
    }
    // Diagnostic bookkeeping only. Check result.registeredClientEvaluatedTypes before
    // interpreting a clear bit: a type never queried for this client is still unknown.
    synchronized int currentFocusMask() { requireOpen();return nativeCurrentFocusMask(handle); }
    static final class AppStateSnapshot {
        final long generation;
        final boolean known;
        private final boolean visible;
        private final long sourceToken;
        final int pid,uid;
        final boolean membershipChanged,refreshActivityState,notifyTopActivity,reportImmersiveUpdate;
        private AppStateSnapshot(long sourceToken,long[] value) {
            this.sourceToken=sourceToken;
            if (value==null || value.length!=6 || value[0]<0 || (value[1]!=0 && value[1]!=1)
                    || (value[2]!=0 && value[2]!=1) || value[3]<0 || value[3]>15)
                throw new IllegalStateException("Invalid native app-state snapshot");
            generation=value[0];known=value[1]==1;visible=value[2]==1;
            membershipChanged=(value[3]&1)!=0;refreshActivityState=(value[3]&2)!=0;
            notifyTopActivity=(value[3]&4)!=0;reportImmersiveUpdate=(value[3]&8)!=0;
            pid=(int)value[4];uid=(int)value[5];
        }
        boolean isVisible() {
            if (!known) throw new IllegalStateException("No recognized service app-state event");
            return visible;
        }
    }
    // Invoke synchronously on the Binder/calling thread, BEFORE async dispatch.
    // These are service-local 0/2 values, never Android Activity or OpenXR enums.
    synchronized AppStateSnapshot applyAppState(int requestedPid,int state) {
        requireOpen();
        return new AppStateSnapshot(handle,nativeAppState(handle,Binder.getCallingPid(),Binder.getCallingUid(),requestedPid,state));
    }
    // For a future endpoint backend: retain the identity captured before dispatch
    // rather than reading Binder identity again on a worker thread.
    synchronized AppStateSnapshot applyAppState(
            org.metaport.port.focus.protocol.VrFocusEndpoint.Caller caller,int requestedPid,int state) {
        requireOpen();java.util.Objects.requireNonNull(caller);
        return new AppStateSnapshot(handle,nativeAppState(handle,caller.pid,caller.uid,requestedPid,state));
    }
    synchronized AppStateSnapshot appStateSnapshot() {
        requireOpen();return new AppStateSnapshot(handle,nativeAppStateSnapshot(handle));
    }
    static final class SessionEvaluation {
        final long sessionGeneration;
        final FocusPolicyResult policy;
        private SessionEvaluation(long generation,FocusPolicyResult result) {
            sessionGeneration=generation;policy=result;
        }
    }
    // Only the session/rendering channel is bound here. The remaining frame must
    // still contain coherent, resolved observations; no complete producer exists yet.
    synchronized SessionEvaluation evaluateWithSession(FocusPolicyFrame frame,AppStateSnapshot observed) {
        requireOpen();java.util.Objects.requireNonNull(frame);java.util.Objects.requireNonNull(observed);
        if (observed.sourceToken!=handle) throw new IllegalArgumentException("Foreign session snapshot");
        if (!observed.known) throw new IllegalStateException("No recognized service app-state event");
        byte[] result=nativeEvaluateSession(handle,observed.sourceToken,observed.generation,frame.encode());
        return new SessionEvaluation(observed.generation,FocusPolicyResult.decode(result));
    }
    static final class WindowSnapshot {
        private final long token,source;
        final long generation;
        final boolean known;
        private WindowSnapshot(long token,long[] values) {
            if (values==null || values.length!=3 || values[0]<=0 || values[1]<=0 || (values[2]!=0 && values[2]!=1))
                throw new IllegalStateException("Invalid window observation");
            this.token=token;source=values[0];generation=values[1];known=values[2]==1;
        }
    }
    static final class ObservedEvaluation {
        final long sessionGeneration,windowGeneration;
        final FocusPolicyResult policy;
        private ObservedEvaluation(long session,long window,FocusPolicyResult policy) {
            sessionGeneration=session;windowGeneration=window;this.policy=policy;
        }
    }
    synchronized long attachWindowSource() { requireOpen();return nativeAttachWindow(handle); }
    synchronized void detachWindowSource(long source) { if (handle!=0) nativeDetachWindow(handle,source); }
    synchronized boolean isClosed() { return handle==0; }
    synchronized WindowSnapshot observeWindow(long source,AppWindowFocusBackend.Snapshot snapshot) {
        requireOpen();java.util.Objects.requireNonNull(snapshot);
        int[] identity=nativeIdentity(handle);
        boolean primaryWindow=false;
        for (AppWindowFocusBackend.FocusedWindow window:snapshot.focusedWindows) {
            if (window.pid!=identity[0] || window.uid!=identity[1] || window.displayId<0)
                throw new IllegalArgumentException("Foreign window identity");
            if (window.displayId==android.view.Display.DEFAULT_DISPLAY) primaryWindow=true;
        }
        // An empty/closed/late-started observer cannot establish absence of global
        // window focus. Preserve unknown instead of injecting a fabricated null.
        boolean positive=snapshot.observing && primaryWindow;
        return new WindowSnapshot(handle,nativeObserveWindow(handle,source,positive));
    }
    synchronized ObservedEvaluation evaluateWithObservedInputs(FocusPolicyFrame frame,
            AppStateSnapshot session,WindowSnapshot window) {
        requireOpen();java.util.Objects.requireNonNull(frame);
        java.util.Objects.requireNonNull(session);java.util.Objects.requireNonNull(window);
        if (session.sourceToken!=handle || window.token!=handle) throw new IllegalArgumentException("Foreign input snapshot");
        if (!session.known || !window.known) throw new IllegalStateException("Required input unavailable");
        byte[] value=nativeEvaluateObserved(handle,session.sourceToken,session.generation,
                window.source,window.generation,frame.encode());
        return new ObservedEvaluation(session.generation,window.generation,FocusPolicyResult.decode(value));
    }
    static final class DisplayAccessSnapshot {
        final long generation;
        final boolean mainDisplayFocus;
        final boolean trackedDisplaysChanged;
        final Integer registerDisplayCallbackMask;
        final int[] activeDisplays;
        private DisplayAccessSnapshot(int[] values) {
            if (values==null || values.length<6) throw new IllegalStateException("Invalid native display access snapshot");
            long low=Integer.toUnsignedLong(values[0]),high=Integer.toUnsignedLong(values[1]);
            generation=low|(high<<32);
            if (generation<=0 || (values[2]!=0 && values[2]!=1) || (values[3]!=0 && values[3]!=1)
                    || (values[4]!=0 && values[4]!=1))
                throw new IllegalStateException("Invalid native display access snapshot");
            mainDisplayFocus=values[2]==1;
            trackedDisplaysChanged=values[3]==1;
            registerDisplayCallbackMask=values[4]==1?Integer.valueOf(values[5]):null;
            activeDisplays=java.util.Arrays.copyOfRange(values,6,values.length);
        }
    }
    synchronized DisplayAccessSnapshot displayAccessSnapshot() {
        requireOpen();return new DisplayAccessSnapshot(nativeDisplayAccessSnapshot(handle));
    }
    synchronized DisplayAccessSnapshot grantTrackingServiceAccess(
            int callingUid,boolean permissionCacheGranted,int displayId) {
        requireOpen();return new DisplayAccessSnapshot(
                nativeDisplayAccess(handle,callingUid,permissionCacheGranted,displayId,true));
    }
    synchronized DisplayAccessSnapshot revokeTrackingServiceAccess(
            int callingUid,boolean permissionCacheGranted,int displayId) {
        requireOpen();return new DisplayAccessSnapshot(
                nativeDisplayAccess(handle,callingUid,permissionCacheGranted,displayId,false));
    }
    synchronized DisplayAccessSnapshot onDisplayEvent(int displayId,int event) {
        requireOpen();return new DisplayAccessSnapshot(nativeDisplayEvent(handle,displayId,event));
    }
    static final class CachedClientMetadata {
        final int uid,pid;
        final String packageName,metadataProcessName;
        final int allowedBackgroundMask,currentFocusMask;
        private CachedClientMetadata(int uid,int pid,String packageName,String metadataProcessName,
                                     int allowedBackgroundMask,int currentFocusMask) {
            this.uid=uid;this.pid=pid;this.packageName=packageName;
            this.metadataProcessName=metadataProcessName;
            this.allowedBackgroundMask=allowedBackgroundMask;
            this.currentFocusMask=currentFocusMask;
        }
        static CachedClientMetadata decode(byte[] encoded) {
            if (encoded==null || encoded.length<4) throw new IllegalStateException("Invalid native metadata reply");
            java.nio.ByteBuffer in=java.nio.ByteBuffer.wrap(encoded).order(java.nio.ByteOrder.LITTLE_ENDIAN);
            int present=in.getInt();
            if (present==0) {
                if (in.hasRemaining()) throw new IllegalStateException("Trailing metadata reply bytes");
                return null;
            }
            if (present!=1) throw new IllegalStateException("Invalid metadata presence tag");
            int uid=in.getInt(),pid=in.getInt();
            String pkg=readUtf8(in),proc=readUtf8(in);
            int allowed=in.getInt(),current=in.getInt();
            if (in.hasRemaining() || allowed<0 || allowed>3 || current<0 || current>3)
                throw new IllegalStateException("Invalid native metadata reply");
            return new CachedClientMetadata(uid,pid,pkg,proc,allowed,current);
        }
        private static String readUtf8(java.nio.ByteBuffer in) {
            if (in.remaining()<4) throw new IllegalStateException("Truncated metadata string");
            int size=in.getInt();
            if (size<0 || size>FocusPolicyFrame.MAX_TEXT || size>in.remaining())
                throw new IllegalStateException("Invalid metadata string length");
            byte[] bytes=new byte[size];in.get(bytes);
            return new String(bytes,java.nio.charset.StandardCharsets.UTF_8);
        }
    }
    synchronized CachedClientMetadata buildClientMetadata(
            int pid,Integer uid,String processNameTrue,java.util.List<String> packagesForUid,
            boolean backgroundHeadGranted,boolean backgroundInputGranted) {
        requireOpen();
        java.util.Objects.requireNonNull(processNameTrue);
        java.util.Objects.requireNonNull(packagesForUid);
        if (packagesForUid.size()>FocusPolicyFrame.MAX_ROWS)
            throw new IllegalArgumentException("Package list budget exceeded");
        java.nio.ByteBuffer out=java.nio.ByteBuffer.allocate(FocusPolicyFrame.MAX_BYTES)
                .order(java.nio.ByteOrder.LITTLE_ENDIAN);
        out.putInt(pid).putInt(uid!=null?1:0).putInt(uid!=null?uid:0);
        putUtf8(out,processNameTrue);
        out.putInt(packagesForUid.size());
        for (String pkg:packagesForUid) putUtf8(out,pkg);
        out.putInt(backgroundHeadGranted?1:0).putInt(backgroundInputGranted?1:0);
        byte[] packet=java.util.Arrays.copyOf(out.array(),out.position());
        return CachedClientMetadata.decode(nativeBuildClientMetadata(handle,packet));
    }
    synchronized CachedClientMetadata getClientMetadata(int uid,int pid,String refreshedProcessNameTrue) {
        requireOpen();
        byte[] utf8=encodeUtf8(refreshedProcessNameTrue);
        return CachedClientMetadata.decode(nativeGetClientMetadata(handle,uid,pid,utf8));
    }
    synchronized boolean updateCachedCurrentFocus(int uid,int pid,int focusType,boolean focused) {
        requireOpen();
        return nativeUpdateCachedCurrentFocus(handle,uid,pid,focusType,focused);
    }
    private static byte[] encodeUtf8(String value) {
        java.util.Objects.requireNonNull(value);
        if (value.length()>FocusPolicyFrame.MAX_TEXT) throw new IllegalArgumentException("Text budget exceeded");
        try {
            java.nio.ByteBuffer utf8=java.nio.charset.StandardCharsets.UTF_8.newEncoder()
                    .onMalformedInput(java.nio.charset.CodingErrorAction.REPORT)
                    .onUnmappableCharacter(java.nio.charset.CodingErrorAction.REPORT)
                    .encode(java.nio.CharBuffer.wrap(value));
            if (utf8.remaining()>FocusPolicyFrame.MAX_TEXT) throw new IllegalArgumentException("UTF-8 budget exceeded");
            byte[] bytes=new byte[utf8.remaining()];utf8.get(bytes);return bytes;
        } catch (java.nio.charset.CharacterCodingException error) {
            throw new IllegalArgumentException("Invalid UTF-16 input",error);
        }
    }
    private static void putUtf8(java.nio.ByteBuffer out,String value) {
        byte[] bytes=encodeUtf8(value);out.putInt(bytes.length);out.put(bytes);
    }
    private void requireOpen() {
        if (handle==0) throw new IllegalStateException("Closed native focus client");
    }
    @Override public synchronized void close() {
        if (handle!=0) { nativeDestroy(handle); handle=0; }
    }
    private static native int[] nativeDisplayAccess(long handle,int callingUid,boolean permissionGranted,int displayId,boolean grant);
    private static native int[] nativeDisplayEvent(long handle,int displayId,int event);
    private static native int[] nativeDisplayAccessSnapshot(long handle);
    private static native byte[] nativeBuildClientMetadata(long handle,byte[] packet);
    private static native byte[] nativeGetClientMetadata(long handle,int uid,int pid,byte[] refreshedProcessNameUtf8);
    private static native boolean nativeUpdateCachedCurrentFocus(long handle,int uid,int pid,int focusType,boolean focused);
    private static native long nativeAttachWindow(long handle);
    private static native long[] nativeObserveWindow(long handle,long source,boolean positive);
    private static native void nativeDetachWindow(long handle,long source);
    private static native byte[] nativeEvaluateObserved(long handle,long sourceToken,long sessionGeneration,
            long windowSource,long windowGeneration,byte[] packet);
    private static native long[] nativeAppState(long handle,int callerPid,int callerUid,int requestedPid,int state);
    private static native long[] nativeAppStateSnapshot(long handle);
    private static native byte[] nativeEvaluate(long handle,byte[] packet);
    private static native byte[] nativeEvaluateSession(long handle,long sourceToken,long generation,byte[] packet);
    private static native int nativeCurrentFocusMask(long handle);
    private static native long nativeCreate(int pid, int uid);
    private static native int[] nativeIdentity(long handle);
    private static native void nativeDestroy(long handle);
}
