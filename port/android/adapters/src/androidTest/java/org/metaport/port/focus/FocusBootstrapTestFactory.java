// SPDX-License-Identifier: GPL-3.0-only
package org.metaport.port.focus;

import android.app.AppComponentFactory;
import android.app.Application;

/** Test APK only. Does not replace/instrument the original Horizon Application. */
public final class FocusBootstrapTestFactory extends AppComponentFactory {
    static NativeFocusClient constructingClient;
    static String failure;
    @Override public Application instantiateApplication(ClassLoader loader,String className)
            throws InstantiationException,IllegalAccessException,ClassNotFoundException {
        try {
            try { constructingClient=NativeFocusClient.createBeforeApplication(); }
            catch (RuntimeException | LinkageError error) { failure=error.toString(); }
            return super.instantiateApplication(loader,className);
        } finally {
            if (constructingClient!=null) { constructingClient.close();constructingClient=null; }
        }
    }
}
