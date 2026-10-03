// SPDX-License-Identifier: GPL-3.0-only
// Credits: Meta Horizon OS v2.7 — Meta Platforms, Inc.
package org.metaport.horizonos;

import android.Manifest;
import android.app.Activity;
import android.content.ComponentName;
import android.content.Intent;
import android.content.pm.PackageInfo;
import android.content.pm.PackageManager;
import android.graphics.Color;
import android.graphics.Typeface;
import android.graphics.drawable.GradientDrawable;
import android.os.Build;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.view.Gravity;
import android.view.KeyEvent;
import android.view.MotionEvent;
import android.view.View;
import android.view.WindowInsets;
import android.view.WindowInsetsController;
import android.view.WindowManager;
import android.widget.Button;
import android.widget.FrameLayout;
import android.widget.HorizontalScrollView;
import android.widget.LinearLayout;
import android.widget.TextView;
import android.widget.Toast;
import java.util.Locale;
import org.metaport.port.ArCoreTracking;
import org.metaport.port.JoyConInput;
import org.metaport.port.NativeSensors;
import org.metaport.port.focus.VrFocusService;

/** Main VRBox / Google Cardboard Activity for the Meta Horizon OS v2.7 Android Port.
 * Integrates NativeSensors (100Hz NDK IMU), JoyConInput, ArCoreTracking availability,
 * live reconstructed VrFocusService (0x29210..0x2dd60), and StereoCardboardView.
 */
public final class HorizonPortActivity extends Activity implements StereoCardboardView.ActionListener {
    private static final int REQ_CAMERA_PERMISSION = 2701;
    private static final long SENSOR_POLL_INTERVAL_MS = 16L;
    private static final long MAX_SENSOR_AGE_NS = 250_000_000L;

    private final Handler mainHandler = new Handler(Looper.getMainLooper());
    private HorizonPortApplication app;
    private StereoCardboardView stereoView;
    private View centerDividerView;
    private TextView statusBannerText;

    private NativeSensors nativeSensors;
    private JoyConInput joyConInput;
    private int enabledSensorsMask = 0;
    private boolean isResumed = false;
    private float lastTouchX = 0f;
    private float lastTouchY = 0f;

    private final Runnable frameLoop = new Runnable() {
        @Override
        public void run() {
            if (!isResumed) {
                return;
            }
            pollAdaptersAndRefreshUi();
            mainHandler.postDelayed(this, SENSOR_POLL_INTERVAL_MS);
        }
    };

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        getWindow().addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);
        app = (HorizonPortApplication) getApplication();

        try {
            nativeSensors = new NativeSensors(this);
        } catch (RuntimeException ignored) {
            nativeSensors = null;
        }
        try {
            joyConInput = new JoyConInput(this);
        } catch (RuntimeException ignored) {
            joyConInput = null;
        }

        FrameLayout root = new FrameLayout(this);
        root.setBackgroundColor(Color.BLACK);

        stereoView = new StereoCardboardView(this);
        stereoView.setActionListener(this);
        setupTouchLookAndTap(stereoView);
        root.addView(stereoView, new FrameLayout.LayoutParams(
                FrameLayout.LayoutParams.MATCH_PARENT,
                FrameLayout.LayoutParams.MATCH_PARENT));

        // Center VRBox stereo divider line
        centerDividerView = new View(this);
        centerDividerView.setBackgroundColor(Color.argb(180, 90, 185, 255));
        FrameLayout.LayoutParams divParams = new FrameLayout.LayoutParams(
                dp(2), FrameLayout.LayoutParams.MATCH_PARENT, Gravity.CENTER_HORIZONTAL);
        root.addView(centerDividerView, divParams);

        // Top compact telemetry & credit banner
        statusBannerText = new TextView(this);
        statusBannerText.setTextColor(Color.rgb(190, 230, 255));
        statusBannerText.setTextSize(11.5f);
        statusBannerText.setTypeface(Typeface.MONOSPACE, Typeface.BOLD);
        statusBannerText.setPadding(dp(12), dp(4), dp(12), dp(4));
        GradientDrawable topBg = new GradientDrawable();
        topBg.setColor(Color.argb(185, 10, 18, 34));
        topBg.setCornerRadius(dp(14));
        topBg.setStroke(dp(1), Color.argb(160, 70, 165, 255));
        statusBannerText.setBackground(topBg);
        statusBannerText.setText(HorizonPortApplication.LEGAL_CREDITS + " | VRBox/Cardboard Port");
        FrameLayout.LayoutParams topParams = new FrameLayout.LayoutParams(
                FrameLayout.LayoutParams.WRAP_CONTENT,
                FrameLayout.LayoutParams.WRAP_CONTENT,
                Gravity.TOP | Gravity.CENTER_HORIZONTAL);
        topParams.topMargin = dp(8);
        root.addView(statusBannerText, topParams);

        // Bottom interactive Horizon OS Quick Control Dock (Touch / Mouse / Gamepad accessible)
        HorizontalScrollView bottomScroll = new HorizontalScrollView(this);
        bottomScroll.setHorizontalScrollBarEnabled(false);
        LinearLayout dockRow = new LinearLayout(this);
        dockRow.setOrientation(LinearLayout.HORIZONTAL);
        dockRow.setGravity(Gravity.CENTER_VERTICAL);
        dockRow.setPadding(dp(8), dp(5), dp(8), dp(5));
        GradientDrawable dockBg = new GradientDrawable();
        dockBg.setColor(Color.argb(205, 12, 22, 42));
        dockBg.setCornerRadius(dp(18));
        dockBg.setStroke(dp(1), Color.argb(180, 80, 175, 255));
        dockRow.setBackground(dockBg);

        for (int i = 0; i < StereoCardboardView.TAB_TITLES.length; i++) {
            final int tabIdx = i;
            dockRow.addView(makeDockButton(StereoCardboardView.TAB_TITLES[i], false, v -> {
                stereoView.setActiveTab(tabIdx);
                updateStatusBanner();
            }));
        }
        dockRow.addView(makeDockButton("Recenter", true, v -> onRecenterTriggered()));
        dockRow.addView(makeDockButton("Stereo/Mono", true, v -> {
            boolean next = !stereoView.isStereoSplitEnabled();
            stereoView.setStereoSplitEnabled(next);
            centerDividerView.setVisibility(next ? View.VISIBLE : View.GONE);
            updateStatusBanner();
        }));
        dockRow.addView(makeDockButton("IPD +2mm", true, v -> {
            stereoView.adjustIpdMillimeters(2.0f);
            updateStatusBanner();
        }));
        dockRow.addView(makeDockButton("FOV +5°", true, v -> {
            stereoView.adjustFovDegrees(5.0f);
            updateStatusBanner();
        }));
        dockRow.addView(makeDockButton("Action", true, v -> onPrimaryActionTriggered()));

        bottomScroll.addView(dockRow);
        FrameLayout.LayoutParams bottomParams = new FrameLayout.LayoutParams(
                FrameLayout.LayoutParams.WRAP_CONTENT,
                FrameLayout.LayoutParams.WRAP_CONTENT,
                Gravity.BOTTOM | Gravity.CENTER_HORIZONTAL);
        bottomParams.bottomMargin = dp(8);
        root.addView(bottomScroll, bottomParams);

        setContentView(root);
        enterImmersiveFullscreen();
    }

    private Button makeDockButton(String label, boolean accent, View.OnClickListener listener) {
        Button b = new Button(this);
        b.setAllCaps(false);
        b.setText(label);
        b.setTextSize(11.5f);
        b.setTextColor(Color.WHITE);
        b.setTypeface(Typeface.SANS_SERIF, Typeface.BOLD);
        b.setPadding(dp(10), dp(4), dp(10), dp(4));
        b.setMinHeight(dp(32));
        b.setMinimumHeight(dp(32));
        b.setMinWidth(dp(56));
        b.setMinimumWidth(dp(56));
        GradientDrawable bg = new GradientDrawable();
        bg.setCornerRadius(dp(12));
        bg.setColor(accent ? Color.argb(230, 32, 108, 210) : Color.argb(210, 26, 42, 76));
        bg.setStroke(dp(1), accent ? Color.argb(220, 120, 210, 255) : Color.argb(150, 75, 135, 210));
        b.setBackground(bg);
        LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.WRAP_CONTENT,
                dp(34));
        lp.leftMargin = dp(3);
        lp.rightMargin = dp(3);
        b.setLayoutParams(lp);
        b.setOnClickListener(listener);
        return b;
    }

    private void setupTouchLookAndTap(View view) {
        view.setOnTouchListener((v, event) -> {
            switch (event.getActionMasked()) {
                case MotionEvent.ACTION_DOWN:
                    lastTouchX = event.getX();
                    lastTouchY = event.getY();
                    return true;
                case MotionEvent.ACTION_MOVE: {
                    float dx = event.getX() - lastTouchX;
                    float dy = event.getY() - lastTouchY;
                    lastTouchX = event.getX();
                    lastTouchY = event.getY();
                    stereoView.addManualLookDelta(-dx * 0.15f, -dy * 0.12f);
                    return true;
                }
                default:
                    return false;
            }
        });
    }

    @Override
    protected void onResume() {
        super.onResume();
        isResumed = true;
        enterImmersiveFullscreen();
        stereoView.onResume();
        if (nativeSensors != null) {
            try {
                enabledSensorsMask = nativeSensors.start(10000);
            } catch (RuntimeException ignored) {
                enabledSensorsMask = 0;
            }
        }
        if (joyConInput != null && hasWindowFocus()) {
            try {
                joyConInput.start();
            } catch (RuntimeException ignored) {
                // Keep running if input service is restricted.
            }
        }
        app.updateAppStateAndEvaluate(true, hasWindowFocus());
        mainHandler.removeCallbacks(frameLoop);
        mainHandler.post(frameLoop);
    }

    @Override
    protected void onPause() {
        isResumed = false;
        mainHandler.removeCallbacks(frameLoop);
        if (joyConInput != null) {
            try {
                joyConInput.stop();
            } catch (RuntimeException ignored) {
                // Ignore pause cleanup errors.
            }
        }
        if (nativeSensors != null) {
            try {
                nativeSensors.stop();
            } catch (RuntimeException ignored) {
                // Ignore sensor stop errors.
            }
        }
        app.updateAppStateAndEvaluate(false, false);
        stereoView.onPause();
        super.onPause();
    }

    @Override
    protected void onDestroy() {
        mainHandler.removeCallbacks(frameLoop);
        if (joyConInput != null) {
            try {
                joyConInput.close();
            } catch (RuntimeException ignored) {
                // Ignore close errors.
            }
            joyConInput = null;
        }
        if (nativeSensors != null) {
            try {
                nativeSensors.close();
            } catch (RuntimeException ignored) {
                // Ignore close errors.
            }
            nativeSensors = null;
        }
        super.onDestroy();
    }

    @Override
    public void onWindowFocusChanged(boolean hasFocus) {
        super.onWindowFocusChanged(hasFocus);
        if (hasFocus) {
            enterImmersiveFullscreen();
        }
        if (joyConInput != null) {
            try {
                if (hasFocus && isResumed) {
                    joyConInput.start();
                } else {
                    joyConInput.stop();
                }
            } catch (RuntimeException ignored) {
                // Ignore transient focus changes.
            }
        }
        app.updateAppStateAndEvaluate(isResumed, hasFocus);
    }

    @Override
    public boolean dispatchKeyEvent(KeyEvent event) {
        if (joyConInput != null && joyConInput.onKeyEvent(event)) {
            return true;
        }
        if (event.getAction() == KeyEvent.ACTION_DOWN) {
            int keyCode = event.getKeyCode();
            if (keyCode == KeyEvent.KEYCODE_VOLUME_UP
                    || keyCode == KeyEvent.KEYCODE_DPAD_RIGHT
                    || keyCode == KeyEvent.KEYCODE_BUTTON_R1) {
                stereoView.setActiveTab(stereoView.getActiveTab() + 1);
                updateStatusBanner();
                return true;
            }
            if (keyCode == KeyEvent.KEYCODE_DPAD_LEFT
                    || keyCode == KeyEvent.KEYCODE_BUTTON_L1) {
                stereoView.setActiveTab(stereoView.getActiveTab() - 1);
                updateStatusBanner();
                return true;
            }
            if (keyCode == KeyEvent.KEYCODE_VOLUME_DOWN
                    || keyCode == KeyEvent.KEYCODE_ENTER
                    || keyCode == KeyEvent.KEYCODE_DPAD_CENTER
                    || keyCode == KeyEvent.KEYCODE_BUTTON_A) {
                onPrimaryActionTriggered();
                return true;
            }
            if (keyCode == KeyEvent.KEYCODE_R || keyCode == KeyEvent.KEYCODE_BUTTON_B) {
                onRecenterTriggered();
                return true;
            }
        }
        return super.dispatchKeyEvent(event);
    }

    @Override
    public boolean onGenericMotionEvent(MotionEvent event) {
        if (joyConInput != null && joyConInput.onMotionEvent(event)) {
            return true;
        }
        return super.onGenericMotionEvent(event);
    }

    private void pollAdaptersAndRefreshUi() {
        if (nativeSensors != null) {
            try {
                NativeSensors.Snapshot s = nativeSensors.snapshot(MAX_SENSOR_AGE_NS);
                stereoView.updateSensorSnapshot(
                        s.orientationValid,
                        s.enabledSensors != 0 ? s.enabledSensors : enabledSensorsMask,
                        s.orientation,
                        s.angularVelocityRadPerSec,
                        s.accelerationMetersPerSecSquared);
            } catch (RuntimeException ignored) {
                // Keep last pose if snapshot fails.
            }
        }

        String joySummary = "HANDS_REQUESTED (0 Joy-Cons)";
        if (joyConInput != null) {
            try {
                JoyConInput.Snapshot js = joyConInput.snapshot();
                int count = (js.left.connected ? 1 : 0) + (js.right.connected ? 1 : 0);
                joySummary = js.requestedMode.name() + " (" + count + " Joy-Con" + (count == 1 ? "" : "s") + ")";
                if (js.right.stickValid) {
                    stereoView.addManualLookDelta(-js.right.stickX * 1.8f, js.right.stickY * 1.4f);
                } else if (js.left.stickValid) {
                    stereoView.addManualLookDelta(-js.left.stickX * 1.8f, js.left.stickY * 1.4f);
                }
                if ((js.right.pressedSinceRead & (JoyConInput.A | JoyConInput.TRIGGER)) != 0
                        || (js.left.pressedSinceRead & JoyConInput.TRIGGER) != 0) {
                    onPrimaryActionTriggered();
                }
                if ((js.right.pressedSinceRead & JoyConInput.B) != 0) {
                    onRecenterTriggered();
                }
                if ((js.right.pressedSinceRead & JoyConInput.MENU) != 0
                        || (js.left.pressedSinceRead & JoyConInput.MENU) != 0) {
                    stereoView.setActiveTab(stereoView.getActiveTab() + 1);
                }
            } catch (RuntimeException ignored) {
                // Ignore Joy-Con poll error.
            }
        }

        String arStatus;
        try {
            arStatus = ArCoreTracking.availability(this).name();
        } catch (RuntimeException e) {
            arStatus = "UNAVAILABLE";
        }
        boolean camGranted = checkSelfPermission(Manifest.permission.CAMERA)
                == PackageManager.PERMISSION_GRANTED;

        boolean shellInstalled = false;
        String shellInfo = "com.oculus.vrshell: Not installed on host (Install bundled VrShell Port APK)";
        try {
            PackageInfo pi = getPackageManager().getPackageInfo("com.oculus.vrshell", 0);
            shellInstalled = true;
            shellInfo = "com.oculus.vrshell v" + pi.versionName + " (installed, UID="
                    + (pi.applicationInfo != null ? pi.applicationInfo.uid : 0) + ")";
        } catch (PackageManager.NameNotFoundException ignored) {
            // Not installed alongside yet.
        }

        VrFocusService svc = app.focusService();
        stereoView.updateRuntimeTelemetry(
                app.isHeadFocusGranted(),
                app.isInputFocusGranted(),
                app.isWindowFocused(),
                svc.mainDisplayFocus(),
                svc.isSessionRendering(),
                app.wireTransactionCount(),
                app.topCallbackCount(),
                app.focusCallbackCount(),
                app.lastTopActivity(),
                app.lastImmersiveSummary(),
                arStatus,
                camGranted,
                joySummary,
                shellInstalled,
                shellInfo);
        updateStatusBanner();
    }

    private void updateStatusBanner() {
        String mode = stereoView.isStereoSplitEnabled() ? "STEREO VRBox" : "MONO";
        statusBannerText.setText(String.format(
                Locale.US,
                "%s  |  %s  |  IPD %.0fmm  FOV %.0f°  |  vrfocus HEAD=%s INPUT=%s TX=%d",
                HorizonPortApplication.LEGAL_CREDITS,
                mode,
                stereoView.getIpdMillimeters(),
                stereoView.getFovDegrees(),
                app.isHeadFocusGranted(),
                app.isInputFocusGranted(),
                app.wireTransactionCount()));
    }

    @Override
    public void onSpatialTabSelected(int tabIndex) {
        updateStatusBanner();
        Toast.makeText(
                this,
                "Horizon OS Spatial Panel: " + StereoCardboardView.TAB_TITLES[tabIndex],
                Toast.LENGTH_SHORT).show();
    }

    @Override
    public void onRecenterTriggered() {
        stereoView.recenterHeadPose();
        Toast.makeText(this, "Horizon OS Head Pose Recentered (0.0°)", Toast.LENGTH_SHORT).show();
    }

    @Override
    public void onPrimaryActionTriggered() {
        int tab = stereoView.getActiveTab();
        switch (tab) {
            case 1: // App Library
            case 6: // Bridge & Legal
                if (!tryLaunchOriginalVrShell()) {
                    onRecenterTriggered();
                }
                break;
            case 2: // Quick Settings
                boolean nextStereo = !stereoView.isStereoSplitEnabled();
                stereoView.setStereoSplitEnabled(nextStereo);
                centerDividerView.setVisibility(nextStereo ? View.VISIBLE : View.GONE);
                updateStatusBanner();
                break;
            case 3: // VRBox Optics
                stereoView.adjustIpdMillimeters(2.0f);
                stereoView.recenterHeadPose();
                updateStatusBanner();
                break;
            case 4: // vrfocus & JNI
                app.updateAppStateAndEvaluate(true, hasWindowFocus());
                updateStatusBanner();
                Toast.makeText(
                        this,
                        "Evaluated vrfocus policy (TX=" + app.wireTransactionCount() + ")",
                        Toast.LENGTH_SHORT).show();
                break;
            case 5: // Hands & ARCore
                if (checkSelfPermission(Manifest.permission.CAMERA) != PackageManager.PERMISSION_GRANTED) {
                    requestPermissions(new String[] { Manifest.permission.CAMERA }, REQ_CAMERA_PERMISSION);
                } else {
                    Toast.makeText(
                            this,
                            "CAMERA granted | ARCore=" + ArCoreTracking.availability(this).name(),
                            Toast.LENGTH_SHORT).show();
                }
                break;
            default:
                onRecenterTriggered();
                break;
        }
    }

    private boolean tryLaunchOriginalVrShell() {
        String[] activities = new String[] {
            "com.oculus.vrshell.MainActivity",
            "com.oculus.vrshell.HomeActivity"
        };
        for (String act : activities) {
            try {
                Intent intent = new Intent(Intent.ACTION_MAIN);
                intent.setComponent(new ComponentName("com.oculus.vrshell", act));
                intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
                startActivity(intent);
                return true;
            } catch (Exception ignored) {
                // Try next activity or fallback.
            }
        }
        return false;
    }

    private void enterImmersiveFullscreen() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.R) {
            WindowInsetsController controller = getWindow().getInsetsController();
            if (controller != null) {
                controller.hide(WindowInsets.Type.statusBars() | WindowInsets.Type.navigationBars());
                controller.setSystemBarsBehavior(
                        WindowInsetsController.BEHAVIOR_SHOW_TRANSIENT_BARS_BY_SWIPE);
            }
        } else {
            @SuppressWarnings("deprecation")
            int flags = View.SYSTEM_UI_FLAG_IMMERSIVE_STICKY
                    | View.SYSTEM_UI_FLAG_LAYOUT_STABLE
                    | View.SYSTEM_UI_FLAG_LAYOUT_HIDE_NAVIGATION
                    | View.SYSTEM_UI_FLAG_LAYOUT_FULLSCREEN
                    | View.SYSTEM_UI_FLAG_HIDE_NAVIGATION
                    | View.SYSTEM_UI_FLAG_FULLSCREEN;
            //noinspection deprecation
            getWindow().getDecorView().setSystemUiVisibility(flags);
        }
    }

    private int dp(int value) {
        float density = getResources().getDisplayMetrics().density;
        return Math.round(value * density);
    }
}
