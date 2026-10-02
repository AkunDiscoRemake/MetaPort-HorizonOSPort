// SPDX-License-Identifier: GPL-3.0-only
package org.metaport.port.focus;

import android.app.Activity;
import android.app.KeyguardManager;
import android.os.Bundle;
import android.widget.FrameLayout;

/** Instrumentation-only real Android window; not original Horizon UI or a demo. */
public final class FocusTestActivity extends Activity {
    @Override public void onCreate(Bundle state) {
        super.onCreate(state);
        setShowWhenLocked(true);
        setTurnScreenOn(true);
        setContentView(new FrameLayout(this));
        KeyguardManager keyguard = getSystemService(KeyguardManager.class);
        if (keyguard != null) keyguard.requestDismissKeyguard(this, null);
    }
}
