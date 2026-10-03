// SPDX-License-Identifier: GPL-3.0-only
package org.metaport.port.focus;

import android.content.Context;
import android.os.IBinder;
import java.util.HashMap;
import java.util.Map;
import java.util.Objects;
import org.metaport.port.focus.protocol.FocusListeners;
import org.metaport.port.focus.protocol.FocusWire;
import org.metaport.port.focus.protocol.FocusWire.ClientStatus;
import org.metaport.port.focus.protocol.FocusWire.ImmersiveApp;
import org.metaport.port.focus.protocol.VrFocusEndpoint;
import org.metaport.port.focus.protocol.VrFocusEndpoint.Caller;
import org.metaport.port.services.ServiceDirectory;

/** Reconstructed OVR::OS::VrFocusService (0x29210..0x2dd60) over NativeFocusClient and FocusListeners.
 * Does not publish to ServiceDirectory on construction; call publishToDirectory() explicitly.
 */
public final class VrFocusService implements VrFocusEndpoint.Backend, AutoCloseable {
    public static final String PERMISSION_READ_FOCUS_STATE =
            "horizonos.permission.READ_FOCUS_STATE";
    public static final String PERMISSION_GRANT_TRACKING_SERVICE_ACCESS =
            "horizonos.permission.GRANT_TRACKING_SERVICE_ACCESS_TO_DISPLAY";
    public static final int AUDIO_SERVICE_UID = 1041;
    private static final ImmersiveApp EMPTY_IMMERSIVE_FOR_TOP_LISTENER =
            new ImmersiveApp("", 0, 0, false);

    public interface PermissionChecker {
        boolean checkPermission(String permission, int pid, int uid);
    }

    private final Object stateLock = new Object();
    private final NativeFocusClient client;
    private final PermissionChecker permissionChecker;
    private final FocusListeners listeners;
    private final VrFocusEndpoint endpoint;
    private final Map<Integer, Boolean> headDecisions = new HashMap<>();
    private final Map<Integer, Boolean> inputDecisions = new HashMap<>();
    private NativeWindowFocusInput windowInput;
    private String topActivity = "";
    private ImmersiveApp immersiveApp = null;
    private String[] foregroundApps = new String[0];
    private boolean closed = false;

    public VrFocusService(Context context, PermissionChecker permissionChecker) {
        this(new NativeFocusClient(Objects.requireNonNull(context)), permissionChecker);
    }

    private VrFocusService(NativeFocusClient client, PermissionChecker permissionChecker) {
        this.client = Objects.requireNonNull(client);
        this.permissionChecker = Objects.requireNonNull(permissionChecker);
        this.listeners = new FocusListeners((pid, uid, transaction) -> {
            if (!checkCallingPermission(PERMISSION_READ_FOCUS_STATE, pid, uid)) {
                throw new SecurityException("Lacking permission " + PERMISSION_READ_FOCUS_STATE);
            }
        });
        this.endpoint = new VrFocusEndpoint(this);
    }

    public static VrFocusService createBeforeApplication(PermissionChecker permissionChecker) {
        return new VrFocusService(NativeFocusClient.createBeforeApplication(), permissionChecker);
    }

    public void attachMetadataContext(Context context) {
        synchronized (stateLock) {
            requireOpen();
            client.attachMetadataContext(Objects.requireNonNull(context));
        }
    }

    public void startWindowObservation(android.app.Application application) {
        Objects.requireNonNull(application);
        synchronized (stateLock) {
            requireOpen();
            if (windowInput == null) {
                windowInput = new NativeWindowFocusInput(application, client, snapshot -> {});
                windowInput.start();
            }
        }
    }

    public boolean hasObservedWindowFocus() {
        synchronized (stateLock) {
            requireOpen();
            return windowInput != null && windowInput.snapshot().known;
        }
    }

    public VrFocusEndpoint endpoint() {
        return endpoint;
    }

    public void publishToDirectory() {
        synchronized (stateLock) {
            requireOpen();
        }
        ServiceDirectory.publish(FocusWire.NAME, endpoint);
    }

    public NativeFocusClient.Registration registration() {
        synchronized (stateLock) {
            requireOpen();
            return client.registration();
        }
    }

    public boolean mainDisplayFocus() {
        synchronized (stateLock) {
            requireOpen();
            return client.displayAccessSnapshot().mainDisplayFocus;
        }
    }

    public int[] activeDisplays() {
        synchronized (stateLock) {
            requireOpen();
            return client.displayAccessSnapshot().activeDisplays.clone();
        }
    }

    public boolean isSessionRendering() {
        synchronized (stateLock) {
            requireOpen();
            NativeFocusClient.AppStateSnapshot snap = client.appStateSnapshot();
            return snap.known && snap.isVisible();
        }
    }

    public int listenerCount() {
        return listeners.size();
    }

    public boolean checkCallingPermission(String permission, int pid, int uid) {
        Objects.requireNonNull(permission);
        if (uid == AUDIO_SERVICE_UID) {
            return true;
        }
        return permissionChecker.checkPermission(permission, pid, uid);
    }

    @Override
    public void enforceAccess(Caller caller, int transaction) {
        Objects.requireNonNull(caller);
        synchronized (stateLock) {
            requireOpen();
        }
        switch (transaction) {
            case 1:
            case 2:
            case 3:
            case 4:
            case 5:
            case 7:
            case 8:
            case 9:
                if (!checkCallingPermission(PERMISSION_READ_FOCUS_STATE, caller.pid, caller.uid)) {
                    throw new SecurityException("Lacking permission " + PERMISSION_READ_FOCUS_STATE);
                }
                break;
            case 6:
                // 0x2c450 setAppState enforces caller.pid == requestedPid in setAppState().
                break;
            case 10:
            case 11:
                if (!checkCallingPermission(
                        PERMISSION_GRANT_TRACKING_SERVICE_ACCESS, caller.pid, caller.uid)) {
                    throw new SecurityException(
                            "Lacking permission " + PERMISSION_GRANT_TRACKING_SERVICE_ACCESS);
                }
                break;
            default:
                throw new IllegalArgumentException("Unknown focus transaction: " + transaction);
        }
    }

    private static void requireFocusType(int type) {
        if (type != 0 && type != 1) {
            throw new IllegalArgumentException("Invalid focusType: " + type);
        }
    }

    @Override
    public ClientStatus[] getClientFocusStatus(Caller caller, int type, int[] pids) {
        Objects.requireNonNull(caller);
        Objects.requireNonNull(pids);
        requireFocusType(type);
        synchronized (stateLock) {
            requireOpen();
            NativeFocusClient.Registration reg = client.registration();
            Map<Integer, Boolean> table = type == 0 ? headDecisions : inputDecisions;
            ClientStatus[] out = new ClientStatus[pids.length];
            for (int i = 0; i < pids.length; i++) {
                int pid = pids[i];
                boolean hasFocus = Boolean.TRUE.equals(table.get(pid));
                if (pid == reg.pid) {
                    client.updateCachedCurrentFocus(reg.uid, reg.pid, type, hasFocus);
                }
                out[i] = new ClientStatus(pid, hasFocus);
            }
            return out;
        }
    }

    @Override
    public boolean registerVrFocusListener(Caller caller, IBinder listener, int type) {
        Objects.requireNonNull(caller);
        requireFocusType(type);
        return listeners.registerFocus(listener, type);
    }

    @Override
    public boolean unregisterVrFocusListener(Caller caller, int type) {
        Objects.requireNonNull(caller);
        requireFocusType(type);
        return listeners.unregisterFocus(type);
    }

    @Override
    public boolean registerVrTopActivityListener(Caller caller, IBinder listener) {
        Objects.requireNonNull(caller);
        return listeners.registerTop(listener);
    }

    @Override
    public boolean unregisterVrTopActivityListener(Caller caller) {
        Objects.requireNonNull(caller);
        return listeners.unregisterTop();
    }

    @Override
    public void setAppState(Caller caller, int pid, int state) {
        Objects.requireNonNull(caller);
        final boolean notifyTop;
        final String topSnapshot;
        final ImmersiveApp immersiveSnapshot;
        synchronized (stateLock) {
            requireOpen();
            NativeFocusClient.AppStateSnapshot snap = client.applyAppState(caller, pid, state);
            notifyTop = snap.notifyTopActivity;
            topSnapshot = topActivity;
            immersiveSnapshot = immersiveApp != null
                    ? immersiveApp
                    : EMPTY_IMMERSIVE_FOR_TOP_LISTENER;
        }
        if (notifyTop) {
            listeners.notifyTopChanged(topSnapshot, immersiveSnapshot);
        }
    }

    public void setOwnProcessAppState(int state) {
        final boolean notifyTop;
        final String topSnapshot;
        final ImmersiveApp immersiveSnapshot;
        synchronized (stateLock) {
            requireOpen();
            NativeFocusClient.Registration reg = client.registration();
            NativeFocusClient.AppStateSnapshot snap = client.applyAppState(reg.pid, state);
            notifyTop = snap.notifyTopActivity;
            topSnapshot = topActivity;
            immersiveSnapshot = immersiveApp != null
                    ? immersiveApp
                    : EMPTY_IMMERSIVE_FOR_TOP_LISTENER;
        }
        if (notifyTop) {
            listeners.notifyTopChanged(topSnapshot, immersiveSnapshot);
        }
    }

    @Override
    public ImmersiveApp getImmersiveApp(Caller caller) {
        Objects.requireNonNull(caller);
        synchronized (stateLock) {
            requireOpen();
            // Returns null when no immersive app is active; VrFocusEndpoint emits EX_NULL_POINTER (-4).
            return immersiveApp;
        }
    }

    @Override
    public String getTopActivity(Caller caller) {
        Objects.requireNonNull(caller);
        synchronized (stateLock) {
            requireOpen();
            return topActivity;
        }
    }

    @Override
    public String[] getForegroundApps(Caller caller) {
        Objects.requireNonNull(caller);
        synchronized (stateLock) {
            requireOpen();
            return foregroundApps.clone();
        }
    }

    @Override
    public void grantTrackingServiceAccess(Caller caller, int displayId) {
        updateTrackingServiceAccess(caller, displayId, true);
    }

    @Override
    public void revokeTrackingServiceAccess(Caller caller, int displayId) {
        updateTrackingServiceAccess(caller, displayId, false);
    }

    private void updateTrackingServiceAccess(Caller caller, int displayId, boolean grant) {
        Objects.requireNonNull(caller);
        final boolean notifyChanged;
        final String topSnapshot;
        final ImmersiveApp immersiveSnapshot;
        boolean cacheGranted = permissionChecker.checkPermission(
                PERMISSION_GRANT_TRACKING_SERVICE_ACCESS, caller.pid, caller.uid);
        synchronized (stateLock) {
            requireOpen();
            NativeFocusClient.DisplayAccessSnapshot snap = grant
                    ? client.grantTrackingServiceAccess(caller.uid, cacheGranted, displayId)
                    : client.revokeTrackingServiceAccess(caller.uid, cacheGranted, displayId);
            notifyChanged = snap.trackedDisplaysChanged;
            topSnapshot = topActivity;
            immersiveSnapshot = immersiveApp != null
                    ? immersiveApp
                    : EMPTY_IMMERSIVE_FOR_TOP_LISTENER;
        }
        if (notifyChanged) {
            listeners.notifyFocusChanged();
            listeners.notifyTopChanged(topSnapshot, immersiveSnapshot);
        }
    }

    FocusPolicyResult evaluate(FocusPolicyFrame frame, String[] foregroundPackages) {
        Objects.requireNonNull(frame);
        Objects.requireNonNull(foregroundPackages);
        for (String pkg : foregroundPackages) {
            Objects.requireNonNull(pkg);
        }
        final FocusPolicyResult result;
        final String topSnapshot;
        final ImmersiveApp immersiveSnapshot;
        synchronized (stateLock) {
            requireOpen();
            result = client.evaluate(frame);
            applyPolicyResultLocked(result, foregroundPackages);
            topSnapshot = topActivity;
            immersiveSnapshot = immersiveApp != null
                    ? immersiveApp
                    : EMPTY_IMMERSIVE_FOR_TOP_LISTENER;
        }
        listeners.notifyFocusChanged();
        listeners.notifyTopChanged(topSnapshot, immersiveSnapshot);
        return result;
    }

    public boolean evaluateOwnProcess(
            int type,
            long observedEpochMillis,
            String packageName,
            String processName,
            boolean backgroundHeadGranted,
            boolean backgroundInputGranted,
            boolean isActivity,
            boolean isPanel,
            boolean isTopOnOwnDisplay,
            boolean isTopOnAnyDisplay,
            boolean hasWindowFocus) {
        requireFocusType(type);
        Objects.requireNonNull(packageName);
        Objects.requireNonNull(processName);
        final FocusPolicyResult result;
        final String topSnapshot;
        final ImmersiveApp immersiveSnapshot;
        final int ownPid;
        synchronized (stateLock) {
            requireOpen();
            NativeFocusClient.Registration reg = client.registration();
            ownPid = reg.pid;
            client.buildClientMetadata(
                    reg.pid,
                    reg.uid,
                    processName,
                    java.util.Collections.singletonList(packageName),
                    backgroundHeadGranted,
                    backgroundInputGranted);
            int bgMask = (backgroundHeadGranted ? 1 : 0) | (backgroundInputGranted ? 2 : 0);
            FocusPolicyFrame.Client self = new FocusPolicyFrame.Client(reg.uid, reg.pid);
            FocusPolicyFrame.Request[] requests = new FocusPolicyFrame.Request[] {
                new FocusPolicyFrame.Request(self, bgMask)
            };
            FocusPolicyFrame.Client[] activities = isActivity
                    ? new FocusPolicyFrame.Client[] { self }
                    : new FocusPolicyFrame.Client[0];
            FocusPolicyFrame.Client[] panels = isPanel
                    ? new FocusPolicyFrame.Client[] { self }
                    : new FocusPolicyFrame.Client[0];
            FocusPolicyFrame.Client[] topClients = isTopOnOwnDisplay
                    ? new FocusPolicyFrame.Client[] { self }
                    : new FocusPolicyFrame.Client[0];
            FocusPolicyFrame.Client[] allTopClients = isTopOnAnyDisplay
                    ? new FocusPolicyFrame.Client[] { self }
                    : new FocusPolicyFrame.Client[0];
            FocusPolicyFrame.Client window = hasWindowFocus ? self : null;
            boolean mainDisplayFocus = client.displayAccessSnapshot().mainDisplayFocus;
            FocusPolicyFrame.Metadata meta = new FocusPolicyFrame.Metadata(
                    self, packageName, processName, processName);
            boolean sessionRendering = isSessionRendering();
            FocusPolicyFrame.Metadata[] rendering = sessionRendering
                    ? new FocusPolicyFrame.Metadata[] { meta }
                    : new FocusPolicyFrame.Metadata[0];
            FocusPolicyFrame.Metadata[] liveMetadata = new FocusPolicyFrame.Metadata[] { meta };
            FocusPolicyFrame.Metadata[] fgLookups = isActivity
                    ? new FocusPolicyFrame.Metadata[] { meta }
                    : new FocusPolicyFrame.Metadata[0];
            String[] fgPackages = isActivity ? new String[] { packageName } : new String[0];
            FocusPolicyFrame frame = new FocusPolicyFrame(
                    type,
                    observedEpochMillis,
                    requests,
                    activities,
                    panels,
                    topClients,
                    allTopClients,
                    window,
                    mainDisplayFocus,
                    rendering,
                    liveMetadata,
                    fgLookups,
                    isTopOnOwnDisplay ? processName : "");
            result = client.evaluate(frame);
            applyPolicyResultLocked(result, fgPackages);
            topSnapshot = topActivity;
            immersiveSnapshot = immersiveApp != null
                    ? immersiveApp
                    : EMPTY_IMMERSIVE_FOR_TOP_LISTENER;
        }
        listeners.notifyFocusChanged();
        listeners.notifyTopChanged(topSnapshot, immersiveSnapshot);
        for (FocusPolicyResult.Decision d : result.decisions) {
            if (d.pid == ownPid && d.type == type) {
                return d.focused;
            }
        }
        return false;
    }

    private void applyPolicyResultLocked(FocusPolicyResult result, String[] foregroundPackages) {
        topActivity = result.topActivity;
        immersiveApp = result.immersive != null
                ? new ImmersiveApp(
                        result.immersive.packageName,
                        result.immersive.pid,
                        result.immersive.uid,
                        result.immersive.top)
                : null;
        foregroundApps = foregroundPackages.clone();
        for (FocusPolicyResult.Decision d : result.decisions) {
            Map<Integer, Boolean> table = d.type == 0 ? headDecisions : inputDecisions;
            table.put(d.pid, d.focused);
        }
    }

    private void requireOpen() {
        if (closed) {
            throw new IllegalStateException("VrFocusService is closed");
        }
    }

    @Override
    public void close() {
        NativeWindowFocusInput win;
        synchronized (stateLock) {
            if (closed) {
                return;
            }
            closed = true;
            win = windowInput;
            windowInput = null;
            headDecisions.clear();
            inputDecisions.clear();
        }
        if (win != null) {
            try {
                win.close();
            } catch (RuntimeException ignored) {
                // Close may run off main thread in tests.
            }
        }
        listeners.close();
        client.close();
    }
}
