// SPDX-License-Identifier: GPL-3.0-only
package org.metaport.port.services;

import android.os.Handler;
import android.os.IBinder;
import android.os.Looper;
import android.os.RemoteException;
import android.util.Log;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.Objects;

/** Process-private discovery for actual port services. Never queries system servicemanager.
 * No services are created by this class. Missing/dead services remain unavailable.
 * Providers live for the process lifetime; replacing a live provider is forbidden.
 */
public final class ServiceDirectory {
    private static final Map<String, IBinder> SERVICES = new HashMap<>();
    private static final Map<String, List<ServiceCallback>> WATCHERS = new HashMap<>();
    private static final Handler MAIN = new Handler(Looper.getMainLooper());
    private static final int LIMIT = 64;
    private ServiceDirectory() {}

    private static void name(String name) {
        if (name == null || !name.matches("[A-Za-z0-9_.-]{1,128}"))
            throw new IllegalArgumentException("Invalid local service name");
    }
    public static synchronized IBinder checkService(String name) {
        name(name);
        IBinder binder = SERVICES.get(name);
        return binder != null && binder.isBinderAlive() ? binder : null;
    }
    public static synchronized void registerForNotifications(String name, ServiceCallback callback) {
        name(name); Objects.requireNonNull(callback);
        List<ServiceCallback> callbacks = WATCHERS.get(name);
        if (callbacks == null) {
            if (WATCHERS.size() >= LIMIT) throw new IllegalStateException("Service subscription budget");
            callbacks = new ArrayList<>(); WATCHERS.put(name, callbacks);
        }
        if (callbacks.contains(callback)) return;
        if (callbacks.size() >= LIMIT) throw new IllegalStateException("Callback budget");
        callbacks.add(callback);
        IBinder binder = checkService(name);
        if (binder != null) notifyLater(name, binder, callback);
    }
    public static synchronized void unregisterForNotifications(String name, ServiceCallback callback) {
        name(name);
        List<ServiceCallback> callbacks = WATCHERS.get(name);
        if (callbacks != null) {
            callbacks.remove(callback);
            if (callbacks.isEmpty()) WATCHERS.remove(name);
        }
    }
    /** Only app code can call this: no exported Binder, intent or network registration endpoint. */
    public static synchronized void publish(String name, IBinder binder) {
        name(name); Objects.requireNonNull(binder);
        if (!binder.isBinderAlive()) throw new IllegalArgumentException("Dead service binder");
        IBinder old = SERVICES.get(name);
        if (old == binder) return;
        if (old != null && old.isBinderAlive()) throw new IllegalStateException("Live service already registered");
        if (old == null && SERVICES.size() >= LIMIT) throw new IllegalStateException("Service budget");
        SERVICES.put(name, binder);
        List<ServiceCallback> callbacks = WATCHERS.get(name);
        if (callbacks != null)
            for (ServiceCallback callback : callbacks) notifyLater(name, binder, callback);
    }
    private static void notifyLater(String name, IBinder binder, ServiceCallback callback) {
        MAIN.post(() -> {
            synchronized (ServiceDirectory.class) {
                List<ServiceCallback> callbacks = WATCHERS.get(name);
                if (checkService(name) != binder || callbacks == null || !callbacks.contains(callback)) return;
            }
            try { callback.onRegistration(name, binder); }
            catch (RemoteException failure) {
                unregisterForNotifications(name, callback);
                Log.w("MetaPortServiceDirectory", "Registration recipient disconnected: " + name, failure);
            }
        });
    }
}
