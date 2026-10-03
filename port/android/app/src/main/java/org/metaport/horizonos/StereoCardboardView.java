// SPDX-License-Identifier: GPL-3.0-only
// Credits: Meta Horizon OS v2.7 — Meta Platforms, Inc.
package org.metaport.horizonos;

import android.content.Context;
import android.graphics.Bitmap;
import android.graphics.Canvas;
import android.graphics.Color;
import android.graphics.LinearGradient;
import android.graphics.Paint;
import android.graphics.RectF;
import android.graphics.Shader;
import android.graphics.Typeface;
import android.opengl.GLES20;
import android.opengl.GLSurfaceView;
import android.opengl.GLUtils;
import android.opengl.Matrix;
import android.os.SystemClock;
import java.nio.ByteBuffer;
import java.nio.ByteOrder;
import java.nio.FloatBuffer;
import java.util.Locale;
import javax.microedition.khronos.egl.EGLConfig;
import javax.microedition.khronos.opengles.GL10;

/** Stereoscopic Left/Right Eye OpenGL ES 2.0/3.0 renderer for VRBox / Google Cardboard.
 * Renders the Horizon OS spatial environment (VrShell Home, SystemUX Quick Settings,
 * LibraryPanelApp, SettingsPanelApp, Hand/ARCore status, and live native vrfocus telemetry)
 * with 3DoF IMU head tracking, head-gaze raycasting + dwell, and configurable IPD/FOV.
 */
public final class StereoCardboardView extends GLSurfaceView implements GLSurfaceView.Renderer {
    public interface ActionListener {
        void onSpatialTabSelected(int tabIndex);
        void onRecenterTriggered();
        void onPrimaryActionTriggered();
    }

    public static final String[] TAB_TITLES = new String[] {
        "VrShell Home",
        "App Library",
        "Quick Settings",
        "VRBox Optics",
        "vrfocus & JNI",
        "Hands & ARCore",
        "Bridge & Legal"
    };

    private static final String COLOR_VERT =
            "uniform mat4 uMVP;\n"
            + "attribute vec3 aPos;\n"
            + "attribute vec4 aColor;\n"
            + "varying vec4 vColor;\n"
            + "void main() {\n"
            + "  vColor = aColor;\n"
            + "  gl_Position = uMVP * vec4(aPos, 1.0);\n"
            + "}\n";

    private static final String COLOR_FRAG =
            "precision mediump float;\n"
            + "varying vec4 vColor;\n"
            + "void main() {\n"
            + "  gl_FragColor = vColor;\n"
            + "}\n";

    private static final String TEX_VERT =
            "uniform mat4 uMVP;\n"
            + "attribute vec3 aPos;\n"
            + "attribute vec2 aUv;\n"
            + "varying vec2 vUv;\n"
            + "void main() {\n"
            + "  vUv = aUv;\n"
            + "  gl_Position = uMVP * vec4(aPos, 1.0);\n"
            + "}\n";

    private static final String TEX_FRAG =
            "precision mediump float;\n"
            + "varying vec2 vUv;\n"
            + "uniform sampler2D uTex;\n"
            + "uniform float uHighlight;\n"
            + "void main() {\n"
            + "  vec4 c = texture2D(uTex, vUv);\n"
            + "  gl_FragColor = vec4(c.rgb + vec3(uHighlight * 0.14), c.a);\n"
            + "}\n";

    private final Object stateLock = new Object();
    private ActionListener actionListener;

    // Optics & stereo configuration
    private volatile boolean stereoSplitEnabled = true;
    private volatile boolean barrelVignetteEnabled = true;
    private volatile float ipdMeters = 0.063f; // 63.0 mm default
    private volatile float fovDegrees = 90.0f;

    // Head tracking & gaze state
    private final float[] sensorQuat = new float[] { 0f, 0f, 0f, 1f };
    private final float[] gyroRadSec = new float[] { 0f, 0f, 0f };
    private final float[] accelMps2 = new float[] { 0f, 0f, 0f };
    private volatile boolean sensorValid = false;
    private volatile int enabledSensorMask = 0;
    private volatile float yawOffsetDeg = 0f;
    private volatile float manualYawDeg = 0f;
    private volatile float manualPitchDeg = 0f;
    private volatile float recenterBaseYawDeg = 0f;
    private volatile float currentHeadYawDeg = 0f;
    private volatile float currentHeadPitchDeg = 0f;
    private volatile float currentHeadRollDeg = 0f;

    // Telemetry & UI state
    private volatile int activeTab = 0;
    private volatile int gazedDockIndex = -1;
    private volatile long gazeStartMs = 0L;
    private volatile float gazeDwellProgress = 0f;
    private volatile boolean textureDirty = true;
    private volatile long lastTextureRefreshMs = 0L;

    // Live runtime telemetry strings
    private volatile boolean headFocus = true;
    private volatile boolean inputFocus = true;
    private volatile boolean windowFocus = true;
    private volatile boolean mainDisplayFocus = true;
    private volatile boolean sessionRendering = true;
    private volatile int wireTxCount = 0;
    private volatile int topCbCount = 0;
    private volatile int focusCbCount = 0;
    private volatile String topActivityName = "com.oculus.vrshell";
    private volatile String immersiveAppSummary = "com.oculus.vrshell (top=true)";
    private volatile String arCoreStatus = "UNKNOWN";
    private volatile boolean cameraGranted = false;
    private volatile String joyConSummary = "HANDS_REQUESTED (0 Joy-Cons)";
    private volatile boolean vrShellInstalled = false;
    private volatile String vrShellPackageInfo = "com.oculus.vrshell: Not installed on host";

    // GL handles & matrices
    private int surfaceWidth = 1920;
    private int surfaceHeight = 1080;
    private int colorProgram;
    private int texProgram;
    private int mainPanelTex;
    private int leftWingTex;
    private int rightWingTex;
    private int dockBarTex;

    private FloatBuffer gridBuffer;
    private int gridVertexCount;
    private FloatBuffer quadBuffer;
    private FloatBuffer reticleBuffer;

    private final float[] projMatrix = new float[16];
    private final float[] viewMatrix = new float[16];
    private final float[] modelMatrix = new float[16];
    private final float[] vpMatrix = new float[16];
    private final float[] mvpMatrix = new float[16];

    private Bitmap mainBitmap;
    private Canvas mainCanvas;
    private Bitmap wingBitmap;
    private Canvas wingCanvas;
    private Bitmap dockBitmap;
    private Canvas dockCanvas;
    private final Paint paint = new Paint(Paint.ANTI_ALIAS_FLAG);

    public StereoCardboardView(Context context) {
        super(context);
        setEGLContextClientVersion(2);
        setEGLConfigChooser(8, 8, 8, 8, 16, 0);
        setRenderer(this);
        setRenderMode(GLSurfaceView.RENDERMODE_CONTINUOUSLY);
    }

    public void setActionListener(ActionListener listener) {
        this.actionListener = listener;
    }

    public void updateSensorSnapshot(
            boolean valid,
            int mask,
            float[] quatXyzw,
            float[] gyro,
            float[] accel) {
        synchronized (stateLock) {
            sensorValid = valid;
            enabledSensorMask = mask;
            if (valid && quatXyzw != null && quatXyzw.length == 4) {
                System.arraycopy(quatXyzw, 0, sensorQuat, 0, 4);
            }
            if (gyro != null && gyro.length == 3) {
                System.arraycopy(gyro, 0, gyroRadSec, 0, 3);
            }
            if (accel != null && accel.length == 3) {
                System.arraycopy(accel, 0, accelMps2, 0, 3);
            }
        }
    }

    public void updateRuntimeTelemetry(
            boolean headFocus,
            boolean inputFocus,
            boolean windowFocus,
            boolean mainDisplayFocus,
            boolean sessionRendering,
            int wireTxCount,
            int topCbCount,
            int focusCbCount,
            String topActivityName,
            String immersiveAppSummary,
            String arCoreStatus,
            boolean cameraGranted,
            String joyConSummary,
            boolean vrShellInstalled,
            String vrShellPackageInfo) {
        this.headFocus = headFocus;
        this.inputFocus = inputFocus;
        this.windowFocus = windowFocus;
        this.mainDisplayFocus = mainDisplayFocus;
        this.sessionRendering = sessionRendering;
        this.wireTxCount = wireTxCount;
        this.topCbCount = topCbCount;
        this.focusCbCount = focusCbCount;
        this.topActivityName = topActivityName;
        this.immersiveAppSummary = immersiveAppSummary;
        this.arCoreStatus = arCoreStatus;
        this.cameraGranted = cameraGranted;
        this.joyConSummary = joyConSummary;
        this.vrShellInstalled = vrShellInstalled;
        this.vrShellPackageInfo = vrShellPackageInfo;
        this.textureDirty = true;
    }

    public void setActiveTab(int tab) {
        int clamped = ((tab % TAB_TITLES.length) + TAB_TITLES.length) % TAB_TITLES.length;
        if (this.activeTab != clamped) {
            this.activeTab = clamped;
            this.textureDirty = true;
        }
    }

    public int getActiveTab() {
        return activeTab;
    }

    public void recenterHeadPose() {
        recenterBaseYawDeg = currentHeadYawDeg - manualYawDeg;
        manualYawDeg = 0f;
        manualPitchDeg = 0f;
        textureDirty = true;
    }

    public void addManualLookDelta(float deltaYawDeg, float deltaPitchDeg) {
        manualYawDeg += deltaYawDeg;
        manualPitchDeg = Math.max(-55f, Math.min(55f, manualPitchDeg + deltaPitchDeg));
    }

    public void setStereoSplitEnabled(boolean enabled) {
        this.stereoSplitEnabled = enabled;
        this.textureDirty = true;
    }

    public boolean isStereoSplitEnabled() {
        return stereoSplitEnabled;
    }

    public void setBarrelVignetteEnabled(boolean enabled) {
        this.barrelVignetteEnabled = enabled;
        this.textureDirty = true;
    }

    public boolean isBarrelVignetteEnabled() {
        return barrelVignetteEnabled;
    }

    public void adjustIpdMillimeters(float deltaMm) {
        float mm = ipdMeters * 1000f + deltaMm;
        if (mm > 72f) {
            mm = 56f;
        } else if (mm < 54f) {
            mm = 72f;
        }
        ipdMeters = mm / 1000f;
        textureDirty = true;
    }

    public float getIpdMillimeters() {
        return ipdMeters * 1000f;
    }

    public void adjustFovDegrees(float deltaDeg) {
        float next = fovDegrees + deltaDeg;
        if (next > 110f) {
            next = 80f;
        } else if (next < 80f) {
            next = 110f;
        }
        fovDegrees = next;
        textureDirty = true;
    }

    public float getFovDegrees() {
        return fovDegrees;
    }

    @Override
    public void onSurfaceCreated(GL10 unused, EGLConfig config) {
        GLES20.glClearColor(0.03f, 0.05f, 0.09f, 1.0f);
        GLES20.glEnable(GLES20.GL_DEPTH_TEST);
        GLES20.glEnable(GLES20.GL_BLEND);
        GLES20.glBlendFunc(GLES20.GL_SRC_ALPHA, GLES20.GL_ONE_MINUS_SRC_ALPHA);

        colorProgram = buildProgram(COLOR_VERT, COLOR_FRAG);
        texProgram = buildProgram(TEX_VERT, TEX_FRAG);

        mainPanelTex = createTexture();
        leftWingTex = createTexture();
        rightWingTex = createTexture();
        dockBarTex = createTexture();

        mainBitmap = Bitmap.createBitmap(1024, 640, Bitmap.Config.ARGB_8888);
        mainCanvas = new Canvas(mainBitmap);
        wingBitmap = Bitmap.createBitmap(640, 512, Bitmap.Config.ARGB_8888);
        wingCanvas = new Canvas(wingBitmap);
        dockBitmap = Bitmap.createBitmap(1024, 160, Bitmap.Config.ARGB_8888);
        dockCanvas = new Canvas(dockBitmap);

        buildGeometryBuffers();
        textureDirty = true;
    }

    @Override
    public void onSurfaceChanged(GL10 unused, int width, int height) {
        surfaceWidth = Math.max(1, width);
        surfaceHeight = Math.max(1, height);
    }

    @Override
    public void onDrawFrame(GL10 unused) {
        updateHeadAnglesAndGaze();
        long now = SystemClock.elapsedRealtime();
        if (textureDirty || (now - lastTextureRefreshMs) > 350L) {
            refreshPanelTextures();
            textureDirty = false;
            lastTextureRefreshMs = now;
        }

        GLES20.glViewport(0, 0, surfaceWidth, surfaceHeight);
        GLES20.glClear(GLES20.GL_COLOR_BUFFER_BIT | GLES20.GL_DEPTH_BUFFER_BIT);

        if (stereoSplitEnabled) {
            int halfW = surfaceWidth / 2;
            renderEyeViewport(0, 0, halfW, surfaceHeight, -0.5f * ipdMeters);
            renderEyeViewport(halfW, 0, surfaceWidth - halfW, surfaceHeight, 0.5f * ipdMeters);
        } else {
            renderEyeViewport(0, 0, surfaceWidth, surfaceHeight, 0.0f);
        }
    }

    private void updateHeadAnglesAndGaze() {
        float qx, qy, qz, qw;
        boolean valid;
        synchronized (stateLock) {
            valid = sensorValid;
            qx = sensorQuat[0];
            qy = sensorQuat[1];
            qz = sensorQuat[2];
            qw = sensorQuat[3];
        }
        float sensorYaw = 0f;
        float sensorPitch = 0f;
        float sensorRoll = 0f;
        if (valid) {
            // Convert landscape Android game rotation quaternion to Euler yaw/pitch/roll degrees.
            double sinrCosp = 2.0 * (qw * qx + qy * qz);
            double cosrCosp = 1.0 - 2.0 * (qx * qx + qy * qy);
            double rx = Math.atan2(sinrCosp, cosrCosp);

            double sinp = 2.0 * (qw * qy - qz * qx);
            double ry = Math.abs(sinp) >= 1.0 ? Math.copySign(Math.PI / 2.0, sinp) : Math.asin(sinp);

            double sinyCosp = 2.0 * (qw * qz + qx * qy);
            double cosyCosp = 1.0 - 2.0 * (qy * qy + qz * qz);
            double rz = Math.atan2(sinyCosp, cosyCosp);

            sensorYaw = (float) Math.toDegrees(rz);
            sensorPitch = (float) Math.toDegrees(rx) * 0.45f;
            sensorRoll = (float) Math.toDegrees(ry) * 0.25f;
        }
        currentHeadYawDeg = sensorYaw + manualYawDeg;
        float relYaw = currentHeadYawDeg - recenterBaseYawDeg;
        float relPitch = sensorPitch + manualPitchDeg;
        currentHeadPitchDeg = Math.max(-60f, Math.min(60f, relPitch));
        currentHeadRollDeg = sensorRoll;
        yawOffsetDeg = relYaw;

        // Raycast head gaze against the 3D Universal Menu Dock at z = -1.75m, y in [-0.68, -0.44].
        double yawRad = Math.toRadians(yawOffsetDeg);
        double pitchRad = Math.toRadians(currentHeadPitchDeg);
        float hitX = (float) (-Math.tan(yawRad) * 1.75);
        float hitY = (float) (Math.tan(pitchRad) * 1.75);

        int candidateDock = -1;
        if (hitY >= -0.74f && hitY <= -0.38f && hitX >= -1.15f && hitX <= 1.15f) {
            float norm = (hitX + 1.15f) / 2.30f;
            candidateDock = Math.min(TAB_TITLES.length - 1, Math.max(0, (int) (norm * TAB_TITLES.length)));
        }
        long now = SystemClock.elapsedRealtime();
        if (candidateDock != gazedDockIndex) {
            gazedDockIndex = candidateDock;
            gazeStartMs = now;
            gazeDwellProgress = 0f;
            textureDirty = true;
        } else if (candidateDock >= 0) {
            long elapsed = now - gazeStartMs;
            gazeDwellProgress = Math.min(1.0f, elapsed / 1200.0f);
            if (elapsed >= 1200L && activeTab != candidateDock) {
                activeTab = candidateDock;
                gazeStartMs = now + 800L;
                gazeDwellProgress = 0f;
                textureDirty = true;
                if (actionListener != null) {
                    final int selected = candidateDock;
                    post(() -> actionListener.onSpatialTabSelected(selected));
                }
            }
        } else {
            gazeDwellProgress = 0f;
        }
    }

    private void renderEyeViewport(int x, int y, int w, int h, float eyeOffsetMeters) {
        GLES20.glViewport(x, y, w, h);
        float aspect = (float) w / (float) Math.max(1, h);
        Matrix.perspectiveM(projMatrix, 0, fovDegrees, aspect, 0.1f, 30.0f);

        Matrix.setIdentityM(viewMatrix, 0);
        Matrix.translateM(viewMatrix, 0, -eyeOffsetMeters, 0.0f, 0.0f);
        Matrix.rotateM(viewMatrix, 0, -currentHeadPitchDeg, 1.0f, 0.0f, 0.0f);
        Matrix.rotateM(viewMatrix, 0, -yawOffsetDeg, 0.0f, 1.0f, 0.0f);
        Matrix.multiplyMM(vpMatrix, 0, projMatrix, 0, viewMatrix, 0);

        // 1. Draw Horizon OS Spatial Floor & Boundary Grid
        Matrix.setIdentityM(modelMatrix, 0);
        Matrix.multiplyMM(mvpMatrix, 0, vpMatrix, 0, modelMatrix, 0);
        drawColoredLines(mvpMatrix, gridBuffer, gridVertexCount, 2.0f);

        // 2. Draw Center Main Spatial Panel (VrShell / SystemUX Workspace) at z = -1.95m
        Matrix.setIdentityM(modelMatrix, 0);
        Matrix.translateM(modelMatrix, 0, 0.0f, 0.14f, -1.95f);
        Matrix.scaleM(modelMatrix, 0, 1.15f, 0.72f, 1.0f);
        Matrix.multiplyMM(mvpMatrix, 0, vpMatrix, 0, modelMatrix, 0);
        drawTexturedQuad(mvpMatrix, mainPanelTex, 0.0f);

        // 3. Draw Left Wing Spatial Panel (VrFocusService & ServiceDirectory)
        Matrix.setIdentityM(modelMatrix, 0);
        Matrix.translateM(modelMatrix, 0, -1.55f, 0.14f, -1.72f);
        Matrix.rotateM(modelMatrix, 0, 26.0f, 0.0f, 1.0f, 0.0f);
        Matrix.scaleM(modelMatrix, 0, 0.68f, 0.54f, 1.0f);
        Matrix.multiplyMM(mvpMatrix, 0, vpMatrix, 0, modelMatrix, 0);
        drawTexturedQuad(mvpMatrix, leftWingTex, 0.0f);

        // 4. Draw Right Wing Spatial Panel (NDK Sensors, Hand Pipeline & ARCore)
        Matrix.setIdentityM(modelMatrix, 0);
        Matrix.translateM(modelMatrix, 0, 1.55f, 0.14f, -1.72f);
        Matrix.rotateM(modelMatrix, 0, -26.0f, 0.0f, 1.0f, 0.0f);
        Matrix.scaleM(modelMatrix, 0, 0.68f, 0.54f, 1.0f);
        Matrix.multiplyMM(mvpMatrix, 0, vpMatrix, 0, modelMatrix, 0);
        drawTexturedQuad(mvpMatrix, rightWingTex, 0.0f);

        // 5. Draw Bottom Universal Menu Dock (MetaSystemUI) at z = -1.75m, y = -0.56m
        Matrix.setIdentityM(modelMatrix, 0);
        Matrix.translateM(modelMatrix, 0, 0.0f, -0.56f, -1.75f);
        Matrix.rotateM(modelMatrix, 0, -14.0f, 1.0f, 0.0f, 0.0f);
        Matrix.scaleM(modelMatrix, 0, 1.15f, 0.18f, 1.0f);
        Matrix.multiplyMM(mvpMatrix, 0, vpMatrix, 0, modelMatrix, 0);
        drawTexturedQuad(mvpMatrix, dockBarTex, gazedDockIndex >= 0 ? 0.45f : 0.0f);

        // 6. Draw Head-Locked 3D Gaze Reticle at z = -1.45m in view space
        Matrix.setIdentityM(modelMatrix, 0);
        Matrix.translateM(modelMatrix, 0, -eyeOffsetMeters * 0.35f, 0.0f, -1.45f);
        float scale = gazedDockIndex >= 0 ? (0.028f + 0.012f * gazeDwellProgress) : 0.020f;
        Matrix.scaleM(modelMatrix, 0, scale, scale, 1.0f);
        Matrix.multiplyMM(mvpMatrix, 0, projMatrix, 0, modelMatrix, 0);
        GLES20.glDisable(GLES20.GL_DEPTH_TEST);
        drawColoredLines(mvpMatrix, reticleBuffer, 16, 3.0f);
        GLES20.glEnable(GLES20.GL_DEPTH_TEST);
    }

    private void refreshPanelTextures() {
        drawMainPanelCanvas(mainCanvas, mainBitmap.getWidth(), mainBitmap.getHeight());
        GLES20.glBindTexture(GLES20.GL_TEXTURE_2D, mainPanelTex);
        GLUtils.texImage2D(GLES20.GL_TEXTURE_2D, 0, mainBitmap, 0);

        drawLeftWingCanvas(wingCanvas, wingBitmap.getWidth(), wingBitmap.getHeight());
        GLES20.glBindTexture(GLES20.GL_TEXTURE_2D, leftWingTex);
        GLUtils.texImage2D(GLES20.GL_TEXTURE_2D, 0, wingBitmap, 0);

        drawRightWingCanvas(wingCanvas, wingBitmap.getWidth(), wingBitmap.getHeight());
        GLES20.glBindTexture(GLES20.GL_TEXTURE_2D, rightWingTex);
        GLUtils.texImage2D(GLES20.GL_TEXTURE_2D, 0, wingBitmap, 0);

        drawDockCanvas(dockCanvas, dockBitmap.getWidth(), dockBitmap.getHeight());
        GLES20.glBindTexture(GLES20.GL_TEXTURE_2D, dockBarTex);
        GLUtils.texImage2D(GLES20.GL_TEXTURE_2D, 0, dockBitmap, 0);
    }

    private void drawMainPanelCanvas(Canvas c, int w, int h) {
        c.drawColor(Color.TRANSPARENT, android.graphics.PorterDuff.Mode.CLEAR);
        paint.setShader(new LinearGradient(
                0, 0, 0, h,
                Color.argb(242, 16, 24, 42),
                Color.argb(242, 10, 15, 28),
                Shader.TileMode.CLAMP));
        paint.setStyle(Paint.Style.FILL);
        c.drawRoundRect(new RectF(6, 6, w - 6, h - 6), 36f, 36f, paint);
        paint.setShader(null);

        paint.setStyle(Paint.Style.STROKE);
        paint.setStrokeWidth(4f);
        paint.setColor(Color.argb(210, 56, 152, 255));
        c.drawRoundRect(new RectF(6, 6, w - 6, h - 6), 36f, 36f, paint);

        // Top bar with explicit Meta Horizon OS v2.7 credit
        paint.setStyle(Paint.Style.FILL);
        paint.setColor(Color.argb(255, 24, 38, 68));
        c.drawRoundRect(new RectF(24, 22, w - 24, 92), 20f, 20f, paint);

        paint.setTypeface(Typeface.create(Typeface.SANS_SERIF, Typeface.BOLD));
        paint.setTextSize(26f);
        paint.setColor(Color.rgb(120, 205, 255));
        c.drawText(HorizonPortApplication.LEGAL_CREDITS, 44, 56, paint);

        paint.setTypeface(Typeface.create(Typeface.SANS_SERIF, Typeface.NORMAL));
        paint.setTextSize(18f);
        paint.setColor(Color.rgb(190, 215, 240));
        c.drawText("Quest 3 Firmware 52168470052900520  |  ARM64 VRBox/Cardboard Port  |  Tab: "
                + TAB_TITLES[activeTab], 44, 82, paint);

        // Body content per selected Horizon OS spatial panel
        int y = 140;
        paint.setTypeface(Typeface.create(Typeface.SANS_SERIF, Typeface.BOLD));
        paint.setTextSize(32f);
        paint.setColor(Color.WHITE);
        c.drawText("Horizon OS Spatial Panel — " + TAB_TITLES[activeTab], 44, y, paint);
        y += 44;

        paint.setTypeface(Typeface.create(Typeface.MONOSPACE, Typeface.NORMAL));
        paint.setTextSize(22f);
        paint.setColor(Color.rgb(215, 232, 250));

        String[] lines = buildMainPanelLines();
        for (String line : lines) {
            if (line.startsWith("[OK]") || line.startsWith("HEAD=true")) {
                paint.setColor(Color.rgb(110, 245, 165));
            } else if (line.startsWith("[INFO]") || line.startsWith("•")) {
                paint.setColor(Color.rgb(215, 232, 250));
            } else {
                paint.setColor(Color.rgb(255, 220, 130));
            }
            c.drawText(line, 44, y, paint);
            y += 36;
        }

        // Bottom hint bar inside spatial panel
        paint.setColor(Color.argb(230, 22, 34, 58));
        c.drawRoundRect(new RectF(24, h - 76, w - 24, h - 22), 16f, 16f, paint);
        paint.setTypeface(Typeface.create(Typeface.SANS_SERIF, Typeface.BOLD));
        paint.setTextSize(20f);
        paint.setColor(Color.rgb(150, 220, 255));
        c.drawText("Gaze at bottom 3D Dock (1.2s dwell)  |  Vol+ Next Tab  |  Vol- Action/Recenter  |  Touch HUD below",
                42, h - 42, paint);
    }

    private String[] buildMainPanelLines() {
        switch (activeTab) {
            case 0: // VrShell Home
                return new String[] {
                    "[OK] VrShell / MetaSystemUI Spatial Hierarchy Active (2D Panel + 3D Stereo Compositor)",
                    "[OK] ServiceDirectory(\"vrfocus\") -> Live VrFocusEndpoint (oculus.internal.IVrFocusService)",
                    "HEAD=" + headFocus + "  INPUT=" + inputFocus + "  WINDOW=" + windowFocus
                            + "  MAIN_DISPLAY=" + mainDisplayFocus,
                    "• TopActivity: " + topActivityName + "  |  ImmersiveApp: " + immersiveAppSummary,
                    "• Stereo Mode: " + (stereoSplitEnabled ? "VRBox Split Left/Right" : "Mono Fullscreen")
                            + String.format(Locale.US, "  |  IPD=%.1f mm  |  FOV=%.0f deg",
                                    ipdMeters * 1000f, fovDegrees),
                    "• Head Pose (3DoF IMU): " + String.format(Locale.US,
                            "Yaw=%.1f°  Pitch=%.1f°  Roll=%.1f°",
                            yawOffsetDeg, currentHeadPitchDeg, currentHeadRollDeg),
                    "• Native Libraries: libmetaport_adapters.so (16 KiB ELF aligned, ARM64-v8a)",
                    "• Original VrShell Host Status: " + vrShellPackageInfo
                };
            case 1: // App Library (LibraryPanelApp)
                return new String[] {
                    "[OK] Horizon OS LibraryPanelApp — Ported System & Spatial Modules:",
                    "• 1. com.oculus.vrshell (VrShell Spatial Home & 77 ARM64 Native .so Closure)",
                    "• 2. com.oculus.systemux (SystemUX Quick Settings, Universal Menu & Notifications)",
                    "• 3. com.oculus.panelapp.settings (SettingsPanelApp — Optics, Tracking & Permissions)",
                    "• 4. oculus.internal.IVrFocusService (Native vrfocusserver 0x10b80..0x2dd60 Port)",
                    "• 5. com.oculus.os.platform (BinderClient -> ServiceDirectory App-Local Transport)",
                    "• 6. hzos-framework (2,820 Original HorizonOS / VROS Framework Classes)",
                    "• Action (Vol- / Tap Action): Launch com.oculus.vrshell if installed or Recenter"
                };
            case 2: // Quick Settings (SystemUX)
                return new String[] {
                    "[OK] MetaSystemUI / SystemUX Quick Settings & Notifications:",
                    "• Guardian / SpaceData Boundary: Active (LegacySpace55 / BaseSpaceCb / WindowSpaceCb)",
                    "• Display Tracking Access (0x2cb90): Display 0 Granted (mainDisplayFocus=" + mainDisplayFocus + ")",
                    "• XR Session AppState (0x2c450): " + (sessionRendering ? "STATE=2 (VISIBLE/RENDERING)" : "STATE=0"),
                    "• Audio Server Bypass (0x219f0): UID 1041 verified alongside PermissionCache",
                    "• Thermal & Frame Pacing: 60/90/120 Hz choreographer sync, zero per-frame allocations",
                    "• Notifications: 0 critical alerts | VrFocusEventReporter telemetry active",
                    "• Action (Vol- / Tap Action): Toggle Stereo Split / Mono Inspection View"
                };
            case 3: // VRBox Optics
                return new String[] {
                    "[OK] VRBox / Google Cardboard Optical Calibration & Stereo Viewport:",
                    String.format(Locale.US, "• Interpupillary Distance (IPD): %.1f mm (Range: 54.0 .. 72.0 mm)",
                            ipdMeters * 1000f),
                    String.format(Locale.US, "• Vertical Field of View (FOV): %.0f° (Range: 80° .. 110°)",
                            fovDegrees),
                    "• Stereoscopic Mode: " + (stereoSplitEnabled ? "ENABLED (Left/Right Eye Split)" : "DISABLED (Mono)"),
                    "• Barrel Vignette & Chromatic Frame: " + (barrelVignetteEnabled ? "ENABLED" : "DISABLED"),
                    "• Head Gaze + Dwell (1.2s): ENABLED (Look at any 3D Dock icon to switch panels)",
                    "• Recenter Reference Yaw: " + String.format(Locale.US, "%.1f°", recenterBaseYawDeg),
                    "• Action (Vol- / Tap Action): Cycle IPD Preset (+2.0 mm) & Recenter Pose"
                };
            case 4: // vrfocus & JNI
                return new String[] {
                    "[OK] Reconstructed vrfocusserver (SHA-256 14289b0fca87a4b4...) & libshell.so JNI:",
                    "• Wire Interface: oculus.internal.IVrFocusService (Transactions 1..11 Active)",
                    "• Wire Transactions Executed: " + wireTxCount
                            + "  |  TopCallbacks=" + topCbCount + "  |  FocusCallbacks=" + focusCbCount,
                    "• FocusPolicyCore (0x25460) + CurrentFocusLedger (0x12bc0/0x12de0): Synchronized",
                    "• ClientMetadataCache (0x12320/0x12570): Allowlist & UID-change eviction active",
                    "• ConnectionManager (0x1a4c0/0x22660): Foreground vector order & liveness pruning",
                    "• Shell JNI Contract: 76 verified native methods (ShellApplication / PanelApp / Vulkan)",
                    "• RCpc Lowering Policy: 597 verified ARMv8.3 LDAPR sites -> ARMv8.0 LDAR Acquire"
                };
            case 5: // Hands & ARCore
                return new String[] {
                    "[OK] Smartphone Hand Tracking, Native NEON Kernels & ARCore Passthrough:",
                    "• ARCore Availability on Device: " + arCoreStatus
                            + "  |  CAMERA Permission: " + (cameraGranted ? "GRANTED" : "NOT GRANTED"),
                    "• Controller / Hand Mode: " + joyConSummary,
                    "• Native Hand Palette (hand_palette.cpp): Lossless byte-exact bone transfer ready",
                    "• Native Hand Material (hand_material.cpp): Opacity/finger/wrist scale rules active",
                    "• Native Hand Arena & FMQ (hand_arena_layout / hand_fmq_mapping): 16 KiB page-safe",
                    "• ARM64 NEON Kernels: hand_u8_reduce & hand_saturating_pack verified",
                    "• Action (Vol- / Tap Action): Request CAMERA Permission for Passthrough / ARCore"
                };
            default: // Bridge & Legal
                return new String[] {
                    "[OK] " + HorizonPortApplication.LEGAL_CREDITS,
                    "• " + HorizonPortApplication.AUTHORIZATION_NOTICE,
                    "• Original Quest 3 OTA SHA-256: beea2e092f6239ca21af98466d9b130c22b9ab8822f411b00baf74ebb866858e",
                    "• Original VrShell.apk SHA-256: d3094ee3cb73ef30e151982dfe1f14e46e607a8640cf7f2e37071aeb579a6463",
                    "• Host VrShell Package: " + vrShellPackageInfo,
                    "• ADB / Shizuku Optional Bridge: adb shell pm grant org.metaport.horizonos android.permission.CAMERA",
                    "• License: GPL-3.0-only with preserved Meta Platforms, Inc. copyright & notices",
                    "• Action (Vol- / Tap Action): Launch com.oculus.vrshell (if installed) or Recenter"
                };
        }
    }

    private void drawLeftWingCanvas(Canvas c, int w, int h) {
        c.drawColor(Color.TRANSPARENT, android.graphics.PorterDuff.Mode.CLEAR);
        paint.setStyle(Paint.Style.FILL);
        paint.setColor(Color.argb(235, 14, 24, 44));
        c.drawRoundRect(new RectF(6, 6, w - 6, h - 6), 28f, 28f, paint);
        paint.setStyle(Paint.Style.STROKE);
        paint.setStrokeWidth(3f);
        paint.setColor(Color.argb(200, 72, 180, 255));
        c.drawRoundRect(new RectF(6, 6, w - 6, h - 6), 28f, 28f, paint);

        paint.setStyle(Paint.Style.FILL);
        paint.setTypeface(Typeface.create(Typeface.SANS_SERIF, Typeface.BOLD));
        paint.setTextSize(25f);
        paint.setColor(Color.rgb(110, 210, 255));
        c.drawText("vrfocus Native Service (0x29210)", 28, 48, paint);

        paint.setTypeface(Typeface.create(Typeface.MONOSPACE, Typeface.NORMAL));
        paint.setTextSize(20f);
        paint.setColor(Color.rgb(210, 235, 255));
        String[] rows = new String[] {
            "Service: ServiceDirectory[\"vrfocus\"]",
            "Descriptor: IVrFocusService (1..11)",
            "HEAD Focus (type=0): " + headFocus,
            "INPUT Focus (type=1): " + inputFocus,
            "Window Focus: " + windowFocus,
            "Main Display (id=0): " + mainDisplayFocus,
            "Session Rendering: " + sessionRendering,
            "TopActivity: " + topActivityName,
            "Immersive: " + immersiveAppSummary,
            "Binder Tx Count: " + wireTxCount,
            "Top/Focus Callbacks: " + topCbCount + " / " + focusCbCount
        };
        int y = 92;
        for (String r : rows) {
            c.drawText(r, 28, y, paint);
            y += 36;
        }
    }

    private void drawRightWingCanvas(Canvas c, int w, int h) {
        c.drawColor(Color.TRANSPARENT, android.graphics.PorterDuff.Mode.CLEAR);
        paint.setStyle(Paint.Style.FILL);
        paint.setColor(Color.argb(235, 14, 24, 44));
        c.drawRoundRect(new RectF(6, 6, w - 6, h - 6), 28f, 28f, paint);
        paint.setStyle(Paint.Style.STROKE);
        paint.setStrokeWidth(3f);
        paint.setColor(Color.argb(200, 90, 230, 175));
        c.drawRoundRect(new RectF(6, 6, w - 6, h - 6), 28f, 28f, paint);

        paint.setStyle(Paint.Style.FILL);
        paint.setTypeface(Typeface.create(Typeface.SANS_SERIF, Typeface.BOLD));
        paint.setTextSize(25f);
        paint.setColor(Color.rgb(110, 245, 185));
        c.drawText("NDK Sensors, Hands & Optics", 28, 48, paint);

        float qx, qy, qz, qw, gx, gy, gz, ax, ay, az;
        boolean valid;
        int mask;
        synchronized (stateLock) {
            valid = sensorValid;
            mask = enabledSensorMask;
            qx = sensorQuat[0]; qy = sensorQuat[1]; qz = sensorQuat[2]; qw = sensorQuat[3];
            gx = gyroRadSec[0]; gy = gyroRadSec[1]; gz = gyroRadSec[2];
            ax = accelMps2[0]; ay = accelMps2[1]; az = accelMps2[2];
        }
        paint.setTypeface(Typeface.create(Typeface.MONOSPACE, Typeface.NORMAL));
        paint.setTextSize(20f);
        paint.setColor(Color.rgb(215, 240, 230));
        String[] rows = new String[] {
            "NDK Sensor Mask: 0x" + Integer.toHexString(mask) + " (valid=" + valid + ")",
            String.format(Locale.US, "Quat: [%.2f, %.2f, %.2f, %.2f]", qx, qy, qz, qw),
            String.format(Locale.US, "Euler: Y=%.1f° P=%.1f° R=%.1f°",
                    yawOffsetDeg, currentHeadPitchDeg, currentHeadRollDeg),
            String.format(Locale.US, "Gyro: [%.2f, %.2f, %.2f] rad/s", gx, gy, gz),
            String.format(Locale.US, "Accel: [%.1f, %.1f, %.1f] m/s²", ax, ay, az),
            String.format(Locale.US, "Optics: IPD=%.1fmm FOV=%.0f°", ipdMeters * 1000f, fovDegrees),
            "ARCore 6DoF: " + arCoreStatus,
            "Camera Perm: " + (cameraGranted ? "GRANTED" : "NOT GRANTED"),
            "Input Mode: " + joyConSummary,
            "SpaceData: 0x55 / 0xcb Copiers Ready",
            "Gaze Dwell: " + (gazedDockIndex >= 0
                    ? (TAB_TITLES[gazedDockIndex] + " " + (int) (gazeDwellProgress * 100) + "%")
                    : "Idle (Center Reticle)")
        };
        int y = 92;
        for (String r : rows) {
            c.drawText(r, 28, y, paint);
            y += 36;
        }
    }

    private void drawDockCanvas(Canvas c, int w, int h) {
        c.drawColor(Color.TRANSPARENT, android.graphics.PorterDuff.Mode.CLEAR);
        paint.setStyle(Paint.Style.FILL);
        paint.setColor(Color.argb(240, 18, 28, 52));
        c.drawRoundRect(new RectF(4, 8, w - 4, h - 8), 44f, 44f, paint);
        paint.setStyle(Paint.Style.STROKE);
        paint.setStrokeWidth(3f);
        paint.setColor(Color.argb(220, 80, 175, 255));
        c.drawRoundRect(new RectF(4, 8, w - 4, h - 8), 44f, 44f, paint);

        int count = TAB_TITLES.length;
        float slotW = (w - 32f) / count;
        for (int i = 0; i < count; i++) {
            float left = 16f + i * slotW + 6f;
            float right = left + slotW - 12f;
            boolean active = (i == activeTab);
            boolean gazed = (i == gazedDockIndex);
            paint.setStyle(Paint.Style.FILL);
            if (active) {
                paint.setColor(Color.argb(255, 38, 118, 225));
            } else if (gazed) {
                paint.setColor(Color.argb(235, 45, 85, 155));
            } else {
                paint.setColor(Color.argb(190, 28, 42, 74));
            }
            c.drawRoundRect(new RectF(left, 22f, right, h - 22f), 26f, 26f, paint);

            if (gazed && gazeDwellProgress > 0f) {
                paint.setColor(Color.argb(220, 90, 245, 175));
                float progRight = left + (right - left) * gazeDwellProgress;
                c.drawRoundRect(new RectF(left, h - 32f, progRight, h - 22f), 6f, 6f, paint);
            }

            paint.setTypeface(Typeface.create(Typeface.SANS_SERIF, Typeface.BOLD));
            paint.setTextSize(17f);
            paint.setColor(Color.WHITE);
            String title = TAB_TITLES[i];
            float tw = paint.measureText(title);
            c.drawText(title, left + Math.max(6f, (right - left - tw) * 0.5f), h * 0.56f, paint);
        }
    }

    private void buildGeometryBuffers() {
        // 3D Floor & Room Boundary Grid (-4m..4m at y = -1.25m)
        int lines = 18 * 2 + 4;
        gridVertexCount = lines * 2;
        float[] grid = new float[gridVertexCount * 7];
        int idx = 0;
        float y = -1.25f;
        for (int i = -8; i <= 9; i++) {
            float v = i * 0.5f;
            boolean axis = (i == 0);
            float r = axis ? 0.25f : 0.12f;
            float g = axis ? 0.65f : 0.28f;
            float b = axis ? 0.95f : 0.48f;
            float a = axis ? 0.85f : 0.45f;
            idx = putColoredVertex(grid, idx, v, y, -4.5f, r, g, b, a);
            idx = putColoredVertex(grid, idx, v, y, 1.5f, r, g, b, a);
            idx = putColoredVertex(grid, idx, -4.0f, y, v - 1.5f, r, g, b, a);
            idx = putColoredVertex(grid, idx, 4.0f, y, v - 1.5f, r, g, b, a);
        }
        // Guardian / SpaceData Cyan Room Perimeter at y = -1.22m
        float gy = -1.22f;
        idx = putColoredVertex(grid, idx, -2.2f, gy, -3.2f, 0.2f, 0.95f, 0.85f, 0.95f);
        idx = putColoredVertex(grid, idx, 2.2f, gy, -3.2f, 0.2f, 0.95f, 0.85f, 0.95f);
        idx = putColoredVertex(grid, idx, 2.2f, gy, -3.2f, 0.2f, 0.95f, 0.85f, 0.95f);
        idx = putColoredVertex(grid, idx, 2.2f, gy, 0.8f, 0.2f, 0.95f, 0.85f, 0.95f);
        idx = putColoredVertex(grid, idx, 2.2f, gy, 0.8f, 0.2f, 0.95f, 0.85f, 0.95f);
        idx = putColoredVertex(grid, idx, -2.2f, gy, 0.8f, 0.2f, 0.95f, 0.85f, 0.95f);
        idx = putColoredVertex(grid, idx, -2.2f, gy, 0.8f, 0.2f, 0.95f, 0.85f, 0.95f);
        putColoredVertex(grid, idx, -2.2f, gy, -3.2f, 0.2f, 0.95f, 0.85f, 0.95f);
        gridBuffer = toFloatBuffer(grid);

        // Textured unit quad: x, y, z, u, v
        float[] quad = new float[] {
            -1f,  1f, 0f, 0f, 0f,
            -1f, -1f, 0f, 0f, 1f,
             1f,  1f, 0f, 1f, 0f,
             1f, -1f, 0f, 1f, 1f
        };
        quadBuffer = toFloatBuffer(quad);

        // 3D Gaze Reticle ring (8 segments = 16 vertices)
        float[] ret = new float[16 * 7];
        int rIdx = 0;
        for (int i = 0; i < 8; i++) {
            double a0 = (i * Math.PI * 2.0) / 8.0;
            double a1 = ((i + 1) * Math.PI * 2.0) / 8.0;
            rIdx = putColoredVertex(ret, rIdx,
                    (float) Math.cos(a0), (float) Math.sin(a0), 0f,
                    0.45f, 0.95f, 1.0f, 0.95f);
            rIdx = putColoredVertex(ret, rIdx,
                    (float) Math.cos(a1), (float) Math.sin(a1), 0f,
                    0.45f, 0.95f, 1.0f, 0.95f);
        }
        reticleBuffer = toFloatBuffer(ret);
    }

    private static int putColoredVertex(
            float[] dst, int idx, float x, float y, float z, float r, float g, float b, float a) {
        dst[idx++] = x;
        dst[idx++] = y;
        dst[idx++] = z;
        dst[idx++] = r;
        dst[idx++] = g;
        dst[idx++] = b;
        dst[idx++] = a;
        return idx;
    }

    private void drawColoredLines(float[] mvp, FloatBuffer buf, int vertexCount, float width) {
        GLES20.glUseProgram(colorProgram);
        GLES20.glLineWidth(width);
        int uMvp = GLES20.glGetUniformLocation(colorProgram, "uMVP");
        int aPos = GLES20.glGetAttribLocation(colorProgram, "aPos");
        int aColor = GLES20.glGetAttribLocation(colorProgram, "aColor");
        GLES20.glUniformMatrix4fv(uMvp, 1, false, mvp, 0);
        buf.position(0);
        GLES20.glVertexAttribPointer(aPos, 3, GLES20.GL_FLOAT, false, 7 * 4, buf);
        GLES20.glEnableVertexAttribArray(aPos);
        buf.position(3);
        GLES20.glVertexAttribPointer(aColor, 4, GLES20.GL_FLOAT, false, 7 * 4, buf);
        GLES20.glEnableVertexAttribArray(aColor);
        GLES20.glDrawArrays(GLES20.GL_LINES, 0, vertexCount);
        GLES20.glDisableVertexAttribArray(aPos);
        GLES20.glDisableVertexAttribArray(aColor);
    }

    private void drawTexturedQuad(float[] mvp, int texId, float highlight) {
        GLES20.glUseProgram(texProgram);
        int uMvp = GLES20.glGetUniformLocation(texProgram, "uMVP");
        int uTex = GLES20.glGetUniformLocation(texProgram, "uTex");
        int uHigh = GLES20.glGetUniformLocation(texProgram, "uHighlight");
        int aPos = GLES20.glGetAttribLocation(texProgram, "aPos");
        int aUv = GLES20.glGetAttribLocation(texProgram, "aUv");

        GLES20.glUniformMatrix4fv(uMvp, 1, false, mvp, 0);
        GLES20.glUniform1i(uTex, 0);
        GLES20.glUniform1f(uHigh, highlight);

        GLES20.glActiveTexture(GLES20.GL_TEXTURE0);
        GLES20.glBindTexture(GLES20.GL_TEXTURE_2D, texId);

        quadBuffer.position(0);
        GLES20.glVertexAttribPointer(aPos, 3, GLES20.GL_FLOAT, false, 5 * 4, quadBuffer);
        GLES20.glEnableVertexAttribArray(aPos);
        quadBuffer.position(3);
        GLES20.glVertexAttribPointer(aUv, 2, GLES20.GL_FLOAT, false, 5 * 4, quadBuffer);
        GLES20.glEnableVertexAttribArray(aUv);

        GLES20.glDrawArrays(GLES20.GL_TRIANGLE_STRIP, 0, 4);
        GLES20.glDisableVertexAttribArray(aPos);
        GLES20.glDisableVertexAttribArray(aUv);
    }

    private static int createTexture() {
        int[] ids = new int[1];
        GLES20.glGenTextures(1, ids, 0);
        GLES20.glBindTexture(GLES20.GL_TEXTURE_2D, ids[0]);
        GLES20.glTexParameteri(GLES20.GL_TEXTURE_2D, GLES20.GL_TEXTURE_MIN_FILTER, GLES20.GL_LINEAR);
        GLES20.glTexParameteri(GLES20.GL_TEXTURE_2D, GLES20.GL_TEXTURE_MAG_FILTER, GLES20.GL_LINEAR);
        GLES20.glTexParameteri(GLES20.GL_TEXTURE_2D, GLES20.GL_TEXTURE_WRAP_S, GLES20.GL_CLAMP_TO_EDGE);
        GLES20.glTexParameteri(GLES20.GL_TEXTURE_2D, GLES20.GL_TEXTURE_WRAP_T, GLES20.GL_CLAMP_TO_EDGE);
        return ids[0];
    }

    private static int buildProgram(String vertSrc, String fragSrc) {
        int v = compileShader(GLES20.GL_VERTEX_SHADER, vertSrc);
        int f = compileShader(GLES20.GL_FRAGMENT_SHADER, fragSrc);
        int prog = GLES20.glCreateProgram();
        GLES20.glAttachShader(prog, v);
        GLES20.glAttachShader(prog, f);
        GLES20.glLinkProgram(prog);
        return prog;
    }

    private static int compileShader(int type, String src) {
        int s = GLES20.glCreateShader(type);
        GLES20.glShaderSource(s, src);
        GLES20.glCompileShader(s);
        return s;
    }

    private static FloatBuffer toFloatBuffer(float[] values) {
        ByteBuffer bb = ByteBuffer.allocateDirect(values.length * 4).order(ByteOrder.nativeOrder());
        FloatBuffer fb = bb.asFloatBuffer();
        fb.put(values);
        fb.position(0);
        return fb;
    }
}
