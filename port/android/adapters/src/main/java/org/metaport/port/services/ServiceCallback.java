// SPDX-License-Identifier: GPL-3.0-only
package org.metaport.port.services;

import android.os.Binder;
import android.os.IBinder;
import android.os.IInterface;
import android.os.RemoteException;

/** In-process registration callback, not Android's privileged IServiceCallback. */
public interface ServiceCallback extends IInterface {
    void onRegistration(String name, IBinder service) throws RemoteException;

    abstract class Stub extends Binder implements ServiceCallback {
        public Stub() { super(); }
        @Override public IBinder asBinder() { return this; }
    }
}
