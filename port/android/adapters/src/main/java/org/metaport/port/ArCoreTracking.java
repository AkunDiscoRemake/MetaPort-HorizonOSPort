package org.metaport.port;

import android.Manifest;
import android.app.Activity;
import android.content.Context;
import android.content.pm.PackageManager;
import android.opengl.EGL14;
import android.opengl.GLES20;
import android.os.Looper;

import com.google.ar.core.Anchor;
import com.google.ar.core.ArCoreApk;
import com.google.ar.core.Camera;
import com.google.ar.core.Config;
import com.google.ar.core.Frame;
import com.google.ar.core.Plane;
import com.google.ar.core.Pose;
import com.google.ar.core.Session;
import com.google.ar.core.TrackingState;
import com.google.ar.core.exceptions.CameraNotAvailableException;
import com.google.ar.core.exceptions.UnavailableException;

import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

/** Genuine ARCore camera-world tracking producer. No Horizon ABI has been fabricated.
 * Host owns permission UI, foreground lifecycle, OES texture and render thread.
 * Do NOT open Camera2 separately while this session owns the camera.
 */
public final class ArCoreTracking implements AutoCloseable {
    public enum Availability { READY, INSTALL_REQUIRED, UNSUPPORTED, UNKNOWN }
    public enum State { TRACKING, PAUSED, STOPPED }
    public static final String CLOCK_DOMAIN = "ARCORE_FRAME_TIMESTAMP";
    public static final String COORDINATES = "ARCORE_WORLD_FROM_PHYSICAL_CAMERA_METERS_XYZW";
    private final Thread owner = Thread.currentThread();
    private Session session;
    private final Map<Long, Anchor> anchors = new HashMap<>();
    private long nextAnchor = 1, previousTimestamp = 0, epoch = 0;
    private boolean resumed = false, textureBound = false;

    public static Availability availability(Context context) {
        switch (ArCoreApk.getInstance().checkAvailability(context)) {
            case SUPPORTED_INSTALLED: return Availability.READY;
            case SUPPORTED_NOT_INSTALLED:
            case SUPPORTED_APK_TOO_OLD: return Availability.INSTALL_REQUIRED;
            case UNSUPPORTED_DEVICE_NOT_CAPABLE: return Availability.UNSUPPORTED;
            default: return Availability.UNKNOWN; // Includes async detection in progress.
        }
    }

    /** Explicit host-initiated installation prompt. Returns false while install is pending. */
    public static boolean requestInstallation(Activity activity, boolean userRequested)
            throws UnavailableException {
        if (Looper.myLooper() != Looper.getMainLooper()) throw new IllegalStateException("Installation UI requires main thread");
        return ArCoreApk.getInstance().requestInstall(activity, userRequested) == ArCoreApk.InstallStatus.INSTALLED;
    }

    public ArCoreTracking(Context context) throws UnavailableException {
        if (context.checkSelfPermission(Manifest.permission.CAMERA) != PackageManager.PERMISSION_GRANTED)
            throw new SecurityException("Host must obtain CAMERA permission first");
        if (availability(context) != Availability.READY)
            throw new IllegalStateException("ARCore is not ready; do not synthesize tracking");
        session = new Session(context.getApplicationContext());
        try {
            Config config = new Config(session);
            config.setPlaneFindingMode(Config.PlaneFindingMode.HORIZONTAL_AND_VERTICAL);
            config.setUpdateMode(Config.UpdateMode.LATEST_CAMERA_IMAGE);
            config.setFocusMode(Config.FocusMode.AUTO);
            session.configure(config);
        } catch (RuntimeException e) {
            session.close(); session = null; throw e;
        }
    }

    private void check() {
        if (Thread.currentThread() != owner) throw new IllegalStateException("Use owning render thread");
        if (session == null) throw new IllegalStateException("Closed");
    }
    private void requireGl() {
        if (EGL14.eglGetCurrentContext().equals(EGL14.EGL_NO_CONTEXT))
            throw new IllegalStateException("A current GLES context is required");
    }

    /** OES texture must belong to the current render context; call again after context recreation. */
    public void setCameraTexture(int externalOesTexture) {
        check(); requireGl();
        if (externalOesTexture <= 0 || !GLES20.glIsTexture(externalOesTexture))
            throw new IllegalArgumentException("Texture has not been created/bound by host");
        session.setCameraTextureName(externalOesTexture);
        textureBound = true;
    }

    public void setDisplayGeometry(int rotation, int width, int height) {
        check();
        if (rotation < 0 || rotation > 3 || width <= 0 || height <= 0) throw new IllegalArgumentException("Invalid display geometry");
        session.setDisplayGeometry(rotation, width, height);
    }

    public void resume() throws CameraNotAvailableException {
        check();
        if (resumed) return;
        session.resume(); resumed = true; previousTimestamp = 0; epoch++;
    }
    public void pause() {
        check();
        try { if (resumed) session.pause(); }
        finally { resumed=false; previousTimestamp=0; epoch++; }
    }

    public TrackingFrame update() throws CameraNotAvailableException {
        check(); requireGl();
        if (!resumed || !textureBound) throw new IllegalStateException("Resume and bind an OES camera texture first");
        Frame frame = session.update();
        Camera camera = frame.getCamera();
        long timestamp = frame.getTimestamp();
        boolean fresh = timestamp > previousTimestamp;
        if (timestamp > 0) previousTimestamp = timestamp;
        State state = State.valueOf(camera.getTrackingState().name());
        // Timestamp zero is ARCore's no-camera-frame condition, not a measured pose.
        if (timestamp == 0 && state == State.TRACKING) state = State.PAUSED;
        PoseData pose = state == State.TRACKING ? poseData(camera.getPose()) : null;
        return new TrackingFrame(timestamp, epoch, fresh, state,
                camera.getTrackingFailureReason().name(), pose);
    }

    /** Detected plane extents. Up-facing plane is NOT automatically labelled floor. */
    public List<PlaneData> planes() {
        check();
        if (!resumed) throw new IllegalStateException("Paused");
        List<PlaneData> result = new ArrayList<>();
        for (Plane plane : session.getAllTrackables(Plane.class)) {
            if (plane.getTrackingState() == TrackingState.TRACKING && plane.getSubsumedBy() == null)
                result.add(new PlaneData(plane.getType().name(), poseData(plane.getCenterPose()), plane.getExtentX(), plane.getExtentZ()));
        }
        return result;
    }

    /** Session-local anchor at an ARCore world pose. No cloud/persistence promise. */
    public long createAnchor(PoseData worldPose) {
        check();
        if (!resumed) throw new IllegalStateException("Paused");
        if (anchors.size() >= 64) throw new IllegalStateException("Anchor budget exceeded");
        Anchor anchor = session.createAnchor(new Pose(worldPose.positionMeters(), worldPose.quaternionXyzw()));
        long id = nextAnchor++;
        anchors.put(id, anchor);
        return id;
    }
    public PoseData anchorPose(long id) {
        check();
        if (!resumed) return null;
        Anchor anchor = anchors.get(id);
        if (anchor == null) throw new IllegalArgumentException("Unknown anchor");
        return anchor.getTrackingState() == TrackingState.TRACKING ? poseData(anchor.getPose()) : null;
    }
    public void removeAnchor(long id) {
        check();
        Anchor anchor = anchors.remove(id);
        if (anchor == null) throw new IllegalArgumentException("Unknown anchor");
        anchor.detach();
    }
    @Override public void close() {
        if (Thread.currentThread() != owner) throw new IllegalStateException("Use owning render thread");
        if (session != null) {
            try {
                pause();
                for (Anchor anchor : anchors.values()) anchor.detach();
                anchors.clear();
            } finally { session.close(); session=null; textureBound=false; }
        }
    }
    private static PoseData poseData(Pose pose) { return new PoseData(pose.getTranslation(), pose.getRotationQuaternion()); }

    public static final class TrackingFrame {
        public final long timestampNs, epoch;
        public final boolean newCameraFrame;
        public final State state;
        public final String failureReason;
        /** Null when not tracking; never a fabricated identity/zero pose. */
        public final PoseData worldFromCamera;
        private TrackingFrame(long timestamp, long epoch, boolean fresh, State state, String failure, PoseData pose) {
            timestampNs=timestamp; this.epoch=epoch; newCameraFrame=fresh;
            this.state=state; failureReason=failure; worldFromCamera=pose;
        }
        // No numerical confidence field: ARCore does not provide one here.
    }
    public static final class PlaneData {
        public final String type;
        public final PoseData center;
        public final float extentXMeters, extentZMeters;
        private PlaneData(String type, PoseData center, float x, float z) {
            this.type=type; this.center=center; extentXMeters=x; extentZMeters=z;
        }
    }
}
