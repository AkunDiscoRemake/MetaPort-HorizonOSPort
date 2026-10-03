// SPDX-License-Identifier: GPL-3.0-only
package org.metaport.port.focus.protocol;

import android.app.Service;
import android.content.Intent;
import android.os.Binder;
import android.os.IBinder;
import android.os.Handler;
import android.os.Looper;
import android.os.Parcel;
import android.os.Process;

/** Test-APK-only disposable process for actual kernel Binder death notification. */
public final class RemoteListenerService extends Service {
    @Override public IBinder onBind(Intent intent) {
        return new Binder() {
            @Override protected boolean onTransact(int code,Parcel data,Parcel reply,int flags) {
                if (code!=42) return false;
                data.enforceInterface("org.metaport.test.RemoteListener");
                reply.writeNoException();reply.writeInt(Process.myPid());
                new Handler(Looper.getMainLooper()).postDelayed(() -> Process.killProcess(Process.myPid()),100);
                return true;
            }
        };
    }
}
