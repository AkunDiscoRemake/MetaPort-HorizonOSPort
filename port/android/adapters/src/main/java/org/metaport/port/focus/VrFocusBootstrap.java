// SPDX-License-Identifier: GPL-3.0-only
package org.metaport.port.focus;

import android.app.Application;
import android.os.Process;
import android.os.SystemClock;
import android.util.Log;
import org.metaport.port.focus.protocol.FocusWire;

/**
 * In-process bootstrap that publishes the ported {@link VrFocusService} into
 * {@link org.metaport.port.services.ServiceDirectory} when {@code com.oculus.vrshell}
 * queries {@code "vrfocus"} during {@code ShellApplication.<init>(:153)} before
 * {@code attachBaseContext}.
 */
public final class VrFocusBootstrap {
    private static final String TAG = "MetaPortVrFocus";
    private static final String SHELL_PACKAGE = "com.oculus.vrshell";
    private static VrFocusService instance;

    private VrFocusBootstrap() {}

    public static synchronized void ensurePublished(String name) {
        if (!FocusWire.NAME.equals(name) || instance != null) {
            return;
        }
        String processName = Application.getProcessName();
        if (processName == null || !processName.startsWith(SHELL_PACKAGE)) {
            return;
        }
        final int myPid = Process.myPid();
        final int myUid = Process.myUid();
        VrFocusService service = VrFocusService.createBeforeApplication(
                (permission, pid, uid) -> pid == myPid && uid == myUid);
        service.setOwnProcessAppState(0);
        long now = SystemClock.elapsedRealtime();
        service.evaluateOwnProcess(
                0,
                now,
                SHELL_PACKAGE,
                processName,
                true,
                true,
                true,
                false,
                true,
                true,
                true);
        service.evaluateOwnProcess(
                1,
                now,
                SHELL_PACKAGE,
                processName,
                true,
                true,
                true,
                false,
                true,
                true,
                true);
        service.publishToDirectory();
        instance = service;
        Log.i(TAG, "Published ported VrFocusService to ServiceDirectory(" + name
                + ") for " + processName + " (pid=" + myPid + ")");
    }

    public static synchronized VrFocusService activeService() {
        return instance;
    }
}
