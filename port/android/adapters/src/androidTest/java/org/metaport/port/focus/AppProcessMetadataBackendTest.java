// SPDX-License-Identifier: GPL-3.0-only
package org.metaport.port.focus;

import android.app.Application;
import android.content.Context;
import android.content.ContextWrapper;
import android.content.pm.ApplicationInfo;
import android.os.Process;
import androidx.test.ext.junit.runners.AndroidJUnit4;
import androidx.test.platform.app.InstrumentationRegistry;
import java.util.Arrays;
import org.junit.Test;
import org.junit.runner.RunWith;
import static org.junit.Assert.*;

@RunWith(AndroidJUnit4.class)
public class AppProcessMetadataBackendTest {
    private Context context() {
        return InstrumentationRegistry.getInstrumentation().getTargetContext();
    }
    @Test public void selfMetadataMatchesAndroidIdentityAndPackages() {
        Context context=context();
        AppProcessMetadataBackend.Snapshot actual=new AppProcessMetadataBackend(context).snapshot();
        assertEquals(Process.myPid(),actual.pid);
        assertEquals(Process.myUid(),actual.uid);
        assertEquals(Application.getProcessName(),actual.androidProcessName);
        assertEquals(context.getPackageName(),actual.applicationPackage);
        assertEquals(Arrays.asList(context.getPackageManager().getPackagesForUid(Process.myUid())),
                     actual.packagesForUid);
        assertTrue(actual.packagesForUid.contains(actual.applicationPackage));
        assertTrue(actual.finishedElapsedRealtimeNanos>=actual.startedElapsedRealtimeNanos);
        assertThrows(UnsupportedOperationException.class,actual.packagesForUid::clear);
    }
    @Test public void permissionResultsAreReadFromAndroidWithoutFallbackGrants() {
        Context context=context();
        AppProcessMetadataBackend backend=new AppProcessMetadataBackend(context);
        for (int i=0;i<3;i++) {
            AppProcessMetadataBackend.Snapshot actual=backend.snapshot();
            assertEquals(context.checkPermission(AppProcessMetadataBackend.BACKGROUND_HEAD,
                         Process.myPid(),Process.myUid()),actual.backgroundHeadPermission);
            assertEquals(context.checkPermission(AppProcessMetadataBackend.BACKGROUND_INPUT,
                         Process.myPid(),Process.myUid()),actual.backgroundInputPermission);
        }
    }
    @Test public void foreignContextAndMissingPackageMembershipAreRejected() {
        Context foreign=new ContextWrapper(context()) {
            @Override public ApplicationInfo getApplicationInfo() {
                ApplicationInfo value=new ApplicationInfo(super.getApplicationInfo());
                value.uid=Process.myUid()+1;return value;
            }
        };
        assertThrows(IllegalArgumentException.class,()->new AppProcessMetadataBackend(foreign));
        Context mismatch=new ContextWrapper(context()) {
            @Override public String getPackageName() { return "org.metaport.not.installed.fixture"; }
        };
        assertThrows(IllegalStateException.class,()->new AppProcessMetadataBackend(mismatch).snapshot());
    }
}
