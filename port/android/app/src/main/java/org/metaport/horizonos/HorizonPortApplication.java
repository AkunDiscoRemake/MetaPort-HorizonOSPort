// SPDX-License-Identifier: GPL-3.0-only
// Credits: Meta Horizon OS v2.7 — Meta Platforms, Inc.
package org.metaport.horizonos;

import android.app.Application;
import android.os.Binder;
import android.os.IBinder;
import android.os.Parcel;
import android.os.Process;
import java.util.concurrent.atomic.AtomicBoolean;
import java.util.concurrent.atomic.AtomicInteger;
import java.util.concurrent.atomic.AtomicReference;
import org.metaport.port.focus.VrFocusService;
import org.metaport.port.focus.protocol.FocusWire;
import org.metaport.port.services.ServiceDirectory;

/** Application bootstrap that publishes the reconstructed native vrfocus service
 * before onCreate() (matching ShellApplication.<init>(:153) lifecycle timing).
 */
public final class HorizonPortApplication extends Application {
    public static final String LEGAL_CREDITS =
            "Meta Horizon OS v2.7 — Meta Platforms, Inc.";
    public static final String AUTHORIZATION_NOTICE =
            "Port autorizado do sistema Meta Horizon OS (Quest 3 Build 52168470052900520) "
            + "para smartphones Android ARM64 em VRBox / Google Cardboard.";

    private final VrFocusService focusService;

    private final AtomicInteger wireTransactions = new AtomicInteger(0);
    private final AtomicInteger topCallbackCount = new AtomicInteger(0);
    private final AtomicInteger focusCallbackCount = new AtomicInteger(0);
    private final AtomicBoolean headFocusGranted = new AtomicBoolean(false);
    private final AtomicBoolean inputFocusGranted = new AtomicBoolean(false);
    private final AtomicBoolean windowFocused = new AtomicBoolean(false);
    private final AtomicReference<String> lastTopActivity = new AtomicReference<>("com.oculus.vrshell");
    private final AtomicReference<String> lastImmersiveSummary =
            new AtomicReference<>("com.oculus.vrshell (top=true)");

    private final Binder topActivityListener = new Binder() {
        @Override
        protected boolean onTransact(int code, Parcel data, Parcel reply, int flags) {
            if (code == 1) {
                data.enforceInterface(FocusWire.TOP_LISTENER);
                String top = data.readString();
                int present = data.readInt();
                String pkg = "";
                int pid = 0;
                int uid = 0;
                boolean isTop = false;
                if (present != 0) {
                    data.readInt(); // parcelable byte size
                    pkg = data.readString();
                    pid = data.readInt();
                    uid = data.readInt();
                    isTop = data.readInt() != 0;
                }
                lastTopActivity.set(top != null && !top.isEmpty() ? top : "(none)");
                lastImmersiveSummary.set(
                        (pkg != null && !pkg.isEmpty() ? pkg : "(empty)")
                        + " pid=" + pid + " uid=" + uid + " top=" + isTop);
                topCallbackCount.incrementAndGet();
                return true;
            }
            return false;
        }
    };

    private final Binder headFocusListener = new Binder() {
        @Override
        protected boolean onTransact(int code, Parcel data, Parcel reply, int flags) {
            if (code == 1) {
                data.enforceInterface(FocusWire.FOCUS_LISTENER);
                data.readInt(); // focusType
                focusCallbackCount.incrementAndGet();
                return true;
            }
            return false;
        }
    };

    public HorizonPortApplication() {
        super();
        // Constructed in <init>() before onCreate(), mirroring VrShell's ShellApplication.<init>().
        focusService = VrFocusService.createBeforeApplication(
                (permission, pid, uid) -> pid == Process.myPid() && uid == Process.myUid());
        if (ServiceDirectory.checkService(FocusWire.NAME) == null) {
            focusService.publishToDirectory();
        }
    }

    @Override
    public void onCreate() {
        super.onCreate();
        focusService.attachMetadataContext(this);
        focusService.startWindowObservation(this);
        registerWireListenersAndBootstrap();
    }

    private void registerWireListenersAndBootstrap() {
        IBinder binder = ServiceDirectory.checkService(FocusWire.NAME);
        if (binder == null) {
            return;
        }
        // Transaction 4: registerVrTopActivityListener
        transactOneIntOrBinder(binder, 4, topActivityListener, -1);
        // Transaction 2: registerVrFocusListener(listener, HEAD=0)
        transactOneIntOrBinder(binder, 2, headFocusListener, 0);
        // Transaction 10: grantTrackingServiceAccess(DEFAULT_DISPLAY=0)
        transactDisplayAccess(binder, 10, 0);
    }

    private void transactOneIntOrBinder(IBinder binder, int code, IBinder listener, int arg) {
        Parcel data = Parcel.obtain();
        Parcel reply = Parcel.obtain();
        try {
            data.writeInterfaceToken(FocusWire.SERVICE);
            data.writeStrongBinder(listener);
            if (arg >= 0) {
                data.writeInt(arg);
            }
            if (binder.transact(code, data, reply, 0)) {
                reply.readException();
                wireTransactions.incrementAndGet();
            }
        } catch ( Exception ignored) {
            // Keep startup resilient.
        } finally {
            data.recycle();
            reply.recycle();
        }
    }

    private void transactDisplayAccess(IBinder binder, int code, int displayId) {
        Parcel data = Parcel.obtain();
        Parcel reply = Parcel.obtain();
        try {
            data.writeInterfaceToken(FocusWire.SERVICE);
            data.writeInt(displayId);
            if (binder.transact(code, data, reply, 0)) {
                reply.readException();
                wireTransactions.incrementAndGet();
            }
        } catch (Exception ignored) {
            // Keep startup resilient.
        } finally {
            data.recycle();
            reply.recycle();
        }
    }

    public void updateAppStateAndEvaluate(boolean resumed, boolean hasWindowFocus) {
        boolean observedWin = focusService.hasObservedWindowFocus() || hasWindowFocus;
        windowFocused.set(observedWin);
        IBinder binder = ServiceDirectory.checkService(FocusWire.NAME);
        if (binder != null) {
            Parcel data = Parcel.obtain();
            Parcel reply = Parcel.obtain();
            try {
                // Transaction 6: setAppState(myPid, resumed ? 0 (Visible) : 2 (Stopping))
                data.writeInterfaceToken(FocusWire.SERVICE);
                data.writeInt(Process.myPid());
                data.writeInt(resumed ? 0 : 2);
                if (binder.transact(6, data, reply, 0)) {
                    reply.readException();
                    wireTransactions.incrementAndGet();
                }
            } catch (Exception ignored) {
                // Ignore transient errors.
            } finally {
                data.recycle();
                reply.recycle();
            }
        }
        long now = System.currentTimeMillis();
        boolean head = focusService.evaluateOwnProcess(
                0,
                now,
                "com.oculus.vrshell",
                "com.oculus.vrshell",
                true,
                true,
                resumed,
                false,
                resumed,
                resumed,
                observedWin);
        boolean input = focusService.evaluateOwnProcess(
                1,
                now,
                "com.oculus.vrshell",
                "com.oculus.vrshell",
                true,
                true,
                resumed,
                false,
                resumed,
                resumed,
                observedWin);
        headFocusGranted.set(head);
        inputFocusGranted.set(input);
        queryClientFocusStatusOverWire(0);
        queryClientFocusStatusOverWire(1);
    }

    public boolean queryClientFocusStatusOverWire(int focusType) {
        IBinder binder = ServiceDirectory.checkService(FocusWire.NAME);
        if (binder == null) {
            return false;
        }
        Parcel data = Parcel.obtain();
        Parcel reply = Parcel.obtain();
        try {
            data.writeInterfaceToken(FocusWire.SERVICE);
            data.writeInt(focusType);
            data.writeIntArray(new int[] { Process.myPid() });
            if (binder.transact(1, data, reply, 0)) {
                reply.readException();
                wireTransactions.incrementAndGet();
                int count = reply.readInt();
                if (count == 1 && reply.readInt() != 0) {
                    reply.readInt(); // size
                    reply.readInt(); // pid
                    return reply.readInt() != 0;
                }
            }
        } catch (Exception ignored) {
            // Return false on wire failure.
        } finally {
            data.recycle();
            reply.recycle();
        }
        return false;
    }

    public VrFocusService focusService() {
        return focusService;
    }

    public int wireTransactionCount() {
        return wireTransactions.get();
    }

    public int topCallbackCount() {
        return topCallbackCount.get();
    }

    public int focusCallbackCount() {
        return focusCallbackCount.get();
    }

    public boolean isHeadFocusGranted() {
        return headFocusGranted.get();
    }

    public boolean isInputFocusGranted() {
        return inputFocusGranted.get();
    }

    public boolean isWindowFocused() {
        return windowFocused.get();
    }

    public String lastTopActivity() {
        return lastTopActivity.get();
    }

    public String lastImmersiveSummary() {
        return lastImmersiveSummary.get();
    }
}
