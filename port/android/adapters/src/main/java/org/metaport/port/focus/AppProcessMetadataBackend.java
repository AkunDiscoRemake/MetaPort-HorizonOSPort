// SPDX-License-Identifier: GPL-3.0-only
package org.metaport.port.focus;

import android.app.Application;
import android.content.Context;
import android.content.pm.PackageManager;
import android.os.Process;
import android.os.SystemClock;
import java.util.ArrayList;
import java.util.Collections;
import java.util.List;
import java.util.Objects;

/** Live public-API observations of this process only. Not a global ClientManager.
 * No cached permissions, inferred process names, remote-PID lookup or implicit
 * background grant. Permission results are Android observations, not proof of
 * Meta signing/entitlement, nor authorization for a tracking service.
 */
public final class AppProcessMetadataBackend {
    public static final String BACKGROUND_HEAD =
            "horizonos.permission.ACCESS_BACKGROUND_HEAD_TRACKING";
    public static final String BACKGROUND_INPUT =
            "horizonos.permission.ACCESS_BACKGROUND_INPUT_TRACKING";

    public static final class Snapshot {
        public final int pid;
        public final int uid;
        public final String applicationPackage;
        // Application.getProcessName(), NOT the unported Process::getProcessName(pid,true).
        public final String androidProcessName;
        public final List<String> packagesForUid;
        public final int backgroundHeadPermission;
        public final int backgroundInputPermission;
        // Bounds, not an assertion that separate Android calls are atomic.
        public final long startedElapsedRealtimeNanos;
        public final long finishedElapsedRealtimeNanos;
        private Snapshot(int pid, int uid, String applicationPackage, String processName,
                         List<String> packages, int head, int input, long started, long finished) {
            this.pid=pid; this.uid=uid; this.applicationPackage=applicationPackage;
            androidProcessName=processName;
            packagesForUid=Collections.unmodifiableList(new ArrayList<>(packages));
            backgroundHeadPermission=head; backgroundInputPermission=input;
            startedElapsedRealtimeNanos=started; finishedElapsedRealtimeNanos=finished;
        }
    }

    private final Context context;
    public AppProcessMetadataBackend(Context context) {
        this.context=Objects.requireNonNull(context,"context");
        requireOwnContext();
    }
    private void requireOwnContext() {
        if (context.getApplicationInfo().uid!=Process.myUid())
            throw new IllegalArgumentException("Only this process's application context is supported");
    }
    private int permission(String name, int pid, int uid) {
        int result=context.checkPermission(name,pid,uid);
        if (result!=PackageManager.PERMISSION_GRANTED && result!=PackageManager.PERMISSION_DENIED)
            throw new IllegalStateException("Unknown permission result");
        return result;
    }
    public Snapshot snapshot() {
        long started=SystemClock.elapsedRealtimeNanos();
        requireOwnContext();
        int pid=Process.myPid(), uid=Process.myUid();
        String name=Application.getProcessName();
        String ownPackage=context.getPackageName();
        if (name==null || name.isEmpty() || ownPackage==null || ownPackage.isEmpty())
            throw new IllegalStateException("Own process identity unavailable");
        String[] observed=context.getPackageManager().getPackagesForUid(uid);
        // Unavailable is not an observed empty list; never install a guessed record.
        if (observed==null || observed.length==0)
            throw new IllegalStateException("UID package metadata unavailable");
        List<String> packages=new ArrayList<>();
        for (String value:observed) {
            if (value==null || value.isEmpty())
                throw new IllegalStateException("Incomplete UID package metadata");
            packages.add(value);
        }
        if (!packages.contains(ownPackage))
            throw new IllegalStateException("Application package does not belong to observed UID");
        int head=permission(BACKGROUND_HEAD,pid,uid);
        int input=permission(BACKGROUND_INPUT,pid,uid);
        return new Snapshot(pid,uid,ownPackage,name,packages,head,input,started,
                            SystemClock.elapsedRealtimeNanos());
    }
}
