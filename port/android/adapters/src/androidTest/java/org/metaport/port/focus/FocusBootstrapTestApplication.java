// SPDX-License-Identifier: GPL-3.0-only
package org.metaport.port.focus;

import android.app.Application;
import android.os.Process;

/** Captures proof during construction, when this Application has no base Context. */
public final class FocusBootstrapTestApplication extends Application {
    final boolean contextWasAbsent;
    final boolean identityWasNative;
    final boolean metadataWasUnavailable;
    public FocusBootstrapTestApplication() {
        contextWasAbsent=getBaseContext()==null;
        NativeFocusClient client=FocusBootstrapTestFactory.constructingClient;
        boolean identity=false,metadataUnknown=false;
        if (client!=null) {
            NativeFocusClient.Registration registration=client.registration();
            identity=registration.pid==Process.myPid() && registration.uid==Process.myUid();
            try { client.observeMetadata(); }
            catch (IllegalStateException unavailable) { metadataUnknown=true; }
        }
        identityWasNative=identity;metadataWasUnavailable=metadataUnknown;
    }
}
