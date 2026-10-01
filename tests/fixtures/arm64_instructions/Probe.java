// SPDX-License-Identifier: GPL-3.0-only
package org.metaport.internal.cpuprobe;
import android.app.Instrumentation;
import android.os.Bundle;
public final class Probe extends Instrumentation {
    private String mode;
    public void onCreate(Bundle args) { super.onCreate(args); mode=args.getString("mode", "control"); start(); }
    private static native int execute(int mode);
    public void onStart() {
        Bundle result=new Bundle();
        try {
            System.loadLibrary("instruction_probe");
            int value=execute("lse".equals(mode)?1:"rcpc".equals(mode)?2:"acquire".equals(mode)?3:"rcpc64".equals(mode)?4:"acquire64".equals(mode)?5:0);
            result.putString("value", Integer.toString(value));
            finish(value==7 ? -1:0,result);
        } catch (Throwable error) {
            result.putString("java_error",error.toString()); finish(0,result);
        }
    }
}
