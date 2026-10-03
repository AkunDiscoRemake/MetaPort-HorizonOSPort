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
            int selection;
            switch(mode) {
                case "control": selection=0; break;
                case "lse": selection=1; break;
                case "rcpc": selection=2; break;
                case "acquire": selection=3; break;
                case "rcpc64": selection=4; break;
                case "acquire64": selection=5; break;
                case "rcpc32": selection=6; break;
                case "acquire32": selection=7; break;
                default: throw new IllegalArgumentException("Unknown instruction case: "+mode);
            }
            int value=execute(selection);
            result.putString("value", Integer.toString(value));
            finish(value==7 ? -1:0,result);
        } catch (Throwable error) {
            result.putString("java_error",error.toString()); finish(0,result);
        }
    }
}
