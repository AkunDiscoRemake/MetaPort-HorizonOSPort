// SPDX-License-Identifier: GPL-3.0-only
package org.metaport.port;

import android.content.Context;
import android.graphics.SurfaceTexture;
import android.opengl.GLES20;
import android.opengl.EGL14;
import android.opengl.EGLContext;
import android.view.Surface;
import androidx.test.ext.junit.runners.AndroidJUnit4;
import androidx.test.platform.app.InstrumentationRegistry;
import java.nio.ByteBuffer;
import java.util.concurrent.atomic.AtomicReference;
import org.junit.Test;
import org.junit.runner.RunWith;
import static org.junit.Assert.*;

/** Executes OUR Android/JNI backends. Not original firmware or physical VR validation. */
@RunWith(AndroidJUnit4.class)
public class AdapterRuntimeTest {
    private Context context() {
        return InstrumentationRegistry.getInstrumentation().getTargetContext();
    }
    private void wrongThread(Runnable operation) throws InterruptedException {
        AtomicReference<Throwable> result = new AtomicReference<>();
        Thread other = new Thread(() -> {
            try { operation.run(); } catch (Throwable t) { result.set(t); }
        });
        other.start(); other.join(5000);
        assertFalse("Foreign thread did not finish", other.isAlive());
        assertTrue("Expected thread ownership rejection", result.get() instanceof IllegalStateException);
    }
    @Test(timeout=120000) public void sensorsRepeatedStartStopAndClosedGuards() {
        NativeSensors sensors = new NativeSensors(context());
        try {
            assertThrows(IllegalArgumentException.class, () -> sensors.start(9999));
            assertThrows(IllegalArgumentException.class, () -> sensors.snapshot(-1));
            for (int i=0; i<8; i++) {
                int mask = sensors.start(10000);
                assertEquals(0, mask & ~7); // No sensor presence or fabricated samples assumed.
                NativeSensors.Snapshot live = sensors.snapshot(1_000_000_000L);
                assertEquals(0, live.enabledSensors & ~mask);
                sensors.stop(); sensors.stop();
                NativeSensors.Snapshot stopped = sensors.snapshot(0);
                assertEquals(0, stopped.enabledSensors);
                assertFalse(stopped.orientationValid);
                assertFalse(stopped.gyroscopeValid);
                assertFalse(stopped.accelerationValid);
                assertNull(stopped.orientation);
            }
        } finally { sensors.close(); }
        sensors.close();
        assertThrows(IllegalStateException.class, () -> sensors.start(10000));
        assertThrows(IllegalStateException.class, () -> sensors.snapshot(0));
        assertThrows(IllegalStateException.class, sensors::stop);
    }
    private static class Window implements AutoCloseable {
        final SurfaceTexture texture = new SurfaceTexture(false);
        final Surface surface;
        Window() { texture.setDefaultBufferSize(64,48); surface = new Surface(texture); }
        @Override public void close() { surface.release(); texture.release(); }
    }
    private void renderPixel(EglOutput output) {
        output.makeCurrent();
        assertArrayEquals(new int[]{64,48}, output.surfaceSize());
        assertTrue(output.glesMajorVersion() >= 2);
        GLES20.glViewport(0,0,64,48);
        GLES20.glClearColor(1,0,0,1);
        GLES20.glClear(GLES20.GL_COLOR_BUFFER_BIT);
        ByteBuffer pixel = ByteBuffer.allocateDirect(4);
        GLES20.glReadPixels(0,0,1,1,GLES20.GL_RGBA,GLES20.GL_UNSIGNED_BYTE,pixel);
        assertEquals(GLES20.GL_NO_ERROR, GLES20.glGetError());
        assertTrue((pixel.get(0)&255) >= 250);
        assertEquals(0, pixel.get(1)&255);
        assertEquals(0, pixel.get(2)&255);
        output.present(0); // One queued frame per test surface, no consumer backpressure loop.
    }
    @Test(timeout=120000) public void eglNativeLoadRenderPresentShaderCompileAndClose() throws Exception {
        assertThrows(IllegalArgumentException.class, () -> new EglOutput(null));
        for (int i=0; i<4; i++) {
            try (Window window = new Window()) {
                EglOutput output = new EglOutput(window.surface);
                try {
                    wrongThread(output::makeCurrent);
                    wrongThread(output::close);
                    assertThrows(IllegalArgumentException.class, () -> output.present(-1));
                    // Actual shader compile/link and OES texture lifecycle. NO camera frame claimed.
                    try (PassthroughRenderer renderer = new PassthroughRenderer()) {
                        assertTrue(renderer.cameraTexture() > 0);
                    }
                    renderPixel(output);
                } finally { output.close(); }
                output.close();
                assertThrows(IllegalStateException.class, output::makeCurrent);
                assertThrows(IllegalStateException.class, output::surfaceSize);
            }
        }
    }
    @Test(timeout=120000) public void closingOneOutputDoesNotInvalidateAnother() {
        try (Window first = new Window(); Window second = new Window();
             EglOutput a = new EglOutput(first.surface)) {
            EglOutput b = new EglOutput(second.surface);
            b.close();
            renderPixel(a);
        }
    }
    @Test(timeout=120000) public void rendererRejectsDifferentContextAndClosedUse() throws Exception {
        try (Window first = new Window(); Window second = new Window();
             EglOutput a = new EglOutput(first.surface)) {
            EGLContext cameraContext = EGL14.eglGetCurrentContext();
            ArCoreTracking.requireCameraContext(cameraContext);
            assertThrows(IllegalStateException.class, () -> ArCoreTracking.requireCameraContext(null));
            PassthroughRenderer renderer = new PassthroughRenderer();
            try {
                try (EglOutput b = new EglOutput(second.surface)) {
                    b.makeCurrent();
                    assertThrows(IllegalStateException.class, () -> ArCoreTracking.requireCameraContext(cameraContext));
                    assertThrows(IllegalStateException.class, renderer::cameraTexture);
                    assertThrows(IllegalStateException.class, renderer::close);
                }
                assertThrows(IllegalStateException.class, () -> ArCoreTracking.requireCameraContext(cameraContext));
                a.makeCurrent();
                ArCoreTracking.requireCameraContext(cameraContext);
                assertTrue(renderer.cameraTexture() > 0);
                wrongThread(renderer::cameraTexture);
                assertFalse(renderer.draw(null,0,0,64,48)); // Missing camera frame is not fabricated.
                assertThrows(IllegalArgumentException.class, () -> renderer.draw(null,-1,0,64,48));
                renderer.close();
                assertThrows(IllegalStateException.class, renderer::cameraTexture);
            } finally { a.makeCurrent(); renderer.close(); }
        }
    }
    @Test(timeout=120000) public void inputServiceLifecycleRunsOnMainThread() {
        InstrumentationRegistry.getInstrumentation().runOnMainSync(() -> {
            JoyConInput input = new JoyConInput(context());
            try {
                for (int i=0;i<8;i++) { input.start(); input.start(); input.stop(); input.stop(); }
            } finally { input.close(); }
            input.close();
            assertThrows(IllegalStateException.class, input::start);
        });
    }
}
