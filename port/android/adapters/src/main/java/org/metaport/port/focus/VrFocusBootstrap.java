// SPDX-License-Identifier: GPL-3.0-only
package org.metaport.port.focus;

import android.app.Application;
import android.os.Process;
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
    private static final String SHELL_PROCESS = "com.oculus.vrshell";
    private static final String SHELL_HOME_ACTIVITY = "com.oculus.vrshell.HomeActivity";
    private static VrFocusService instance;

    private VrFocusBootstrap() {}

    public static synchronized void ensurePublished(String name) {
        if (!FocusWire.NAME.equals(name) || instance != null) {
            return;
        }
        String processName = Application.getProcessName();
        if (processName == null || !processName.startsWith(SHELL_PROCESS)) {
            return;
        }
        VrFocusService service = VrFocusService.createBeforeApplication(true, true, true, true);
        int myPid = Process.myPid();
        service.client().applyAppState(myPid, 0);
        service.evaluateOwnProcessFocus(
                SHELL_PROCESS,
                SHELL_HOME_ACTIVITY,
                true,
                true,
                true,
                0);
        service.evaluateOwnProcessFocus(
                SHELL_PROCESS,
                SHELL_HOME_ACTIVITY,
                true,
                true,
                true,
                1);
        service.publishToDirectory();
        instance = service;
        Log.i(TAG, "Published ported VrFocusService to ServiceDirectory(" + name
                + ") for " + processName + " (pid=" + myPid + ")");
    }

    public static synchronized VrFocusService activeService() {
        return instance;
    }
}
