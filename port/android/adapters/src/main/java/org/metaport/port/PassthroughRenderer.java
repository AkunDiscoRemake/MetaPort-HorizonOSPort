// SPDX-License-Identifier: GPL-3.0-only
package org.metaport.port;

import android.opengl.EGL14;
import android.opengl.EGLContext;
import android.opengl.GLES11Ext;
import android.opengl.GLES20;
import com.google.ar.core.Coordinates2d;
import com.google.ar.core.Frame;
import java.nio.ByteBuffer;
import java.nio.ByteOrder;
import java.nio.FloatBuffer;

/** Physical monocular camera background, NOT Quest stereo/depth passthrough.
 * Use on the owning GLES render thread, before the UI pass, while the ARCore
 * session owns the camera. No second Camera2 session, CPU readback or image copy.
 * This pass owns program, texture unit 0, attributes 0/1, ARRAY_BUFFER, viewport,
 * color/depth masks, blend/depth/cull/scissor state. Host MUST rebind its UI state
 * afterward. It never changes framebuffer binding or clears color/depth buffers.
 * Recreate after EGL context loss and rebind the new texture in ArCoreTracking.
 */
public final class PassthroughRenderer implements AutoCloseable {
    private final Thread owner = Thread.currentThread();
    private final EGLContext context = EGL14.eglGetCurrentContext();
    private final FloatBuffer positions = buffer(new float[]{-1,-1, 1,-1, -1,1, 1,1});
    private final FloatBuffer uv = buffer(new float[8]);
    private int program, texture, sampler, vertexBuffer;

    public PassthroughRenderer() {
        checkContext();
        int vertex = 0, fragment = 0;
        try {
            vertex = compile(GLES20.GL_VERTEX_SHADER,
                "attribute vec2 position; attribute vec2 cameraUv; varying vec2 uv;" +
                "void main(){gl_Position=vec4(position,0.,1.);uv=cameraUv;}");
            fragment = compile(GLES20.GL_FRAGMENT_SHADER,
                "#extension GL_OES_EGL_image_external : require\nprecision mediump float;" +
                "uniform samplerExternalOES camera; varying vec2 uv;" +
                "void main(){gl_FragColor=texture2D(camera,uv);}");
            program = GLES20.glCreateProgram();
            GLES20.glAttachShader(program, vertex);
            GLES20.glAttachShader(program, fragment);
            GLES20.glBindAttribLocation(program, 0, "position");
            GLES20.glBindAttribLocation(program, 1, "cameraUv");
            GLES20.glLinkProgram(program);
            int[] ok = new int[1];
            GLES20.glGetProgramiv(program, GLES20.GL_LINK_STATUS, ok, 0);
            if (ok[0] == 0) throw new IllegalStateException(GLES20.glGetProgramInfoLog(program));
            sampler = GLES20.glGetUniformLocation(program, "camera");
            int[] ids = new int[1];
            GLES20.glGenTextures(1, ids, 0); texture = ids[0];
            GLES20.glGenBuffers(1, ids, 0); vertexBuffer = ids[0];
            if (vertexBuffer == 0) throw new IllegalStateException("Vertex buffer allocation failed");
            GLES20.glBindBuffer(GLES20.GL_ARRAY_BUFFER, vertexBuffer);
            GLES20.glBufferData(GLES20.GL_ARRAY_BUFFER, 64, null, GLES20.GL_DYNAMIC_DRAW);
            GLES20.glBufferSubData(GLES20.GL_ARRAY_BUFFER, 0, 32, positions);
            if (texture == 0) throw new IllegalStateException("Camera texture allocation failed");
            GLES20.glActiveTexture(GLES20.GL_TEXTURE0);
            GLES20.glBindTexture(GLES11Ext.GL_TEXTURE_EXTERNAL_OES, texture);
            GLES20.glTexParameteri(GLES11Ext.GL_TEXTURE_EXTERNAL_OES, GLES20.GL_TEXTURE_MIN_FILTER, GLES20.GL_LINEAR);
            GLES20.glTexParameteri(GLES11Ext.GL_TEXTURE_EXTERNAL_OES, GLES20.GL_TEXTURE_MAG_FILTER, GLES20.GL_LINEAR);
            GLES20.glTexParameteri(GLES11Ext.GL_TEXTURE_EXTERNAL_OES, GLES20.GL_TEXTURE_WRAP_S, GLES20.GL_CLAMP_TO_EDGE);
            GLES20.glTexParameteri(GLES11Ext.GL_TEXTURE_EXTERNAL_OES, GLES20.GL_TEXTURE_WRAP_T, GLES20.GL_CLAMP_TO_EDGE);
        } catch (RuntimeException e) {
            release(); throw e;
        } finally {
            if (vertex != 0) GLES20.glDeleteShader(vertex);
            if (fragment != 0) GLES20.glDeleteShader(fragment);
        }
    }
    private static FloatBuffer buffer(float[] values) {
        FloatBuffer b = ByteBuffer.allocateDirect(values.length * 4).order(ByteOrder.nativeOrder()).asFloatBuffer();
        b.put(values).position(0); return b;
    }
    private static int compile(int type, String code) {
        int shader = GLES20.glCreateShader(type);
        GLES20.glShaderSource(shader, code); GLES20.glCompileShader(shader);
        int[] ok = new int[1]; GLES20.glGetShaderiv(shader, GLES20.GL_COMPILE_STATUS, ok, 0);
        if (ok[0] == 0) {
            String log = GLES20.glGetShaderInfoLog(shader); GLES20.glDeleteShader(shader);
            throw new IllegalStateException(log);
        }
        return shader;
    }
    private void checkContext() {
        if (Thread.currentThread() != owner || context.equals(EGL14.EGL_NO_CONTEXT) ||
                !context.equals(EGL14.eglGetCurrentContext()))
            throw new IllegalStateException("Use owning thread and original current EGL context");
    }
    public int cameraTexture() {
        checkContext();
        if (texture == 0) throw new IllegalStateException("Closed");
        return texture;
    }
    // Only ArCoreTracking supplies the current frame; no fabricated pose required.
    boolean draw(Frame frame, int x, int y, int width, int height) {
        cameraTexture();
        if (x < 0 || y < 0 || width <= 0 || height <= 0)
            throw new IllegalArgumentException("Invalid viewport");
        if (frame == null || frame.getTimestamp() <= 0) return false;
        positions.position(0); uv.position(0);
        frame.transformCoordinates2d(Coordinates2d.OPENGL_NORMALIZED_DEVICE_COORDINATES,
                positions, Coordinates2d.TEXTURE_NORMALIZED, uv);
        positions.position(0); uv.position(0);
        GLES20.glViewport(x, y, width, height);
        GLES20.glDisable(GLES20.GL_DEPTH_TEST); GLES20.glDepthMask(false);
        GLES20.glDisable(GLES20.GL_BLEND); GLES20.glDisable(GLES20.GL_CULL_FACE);
        GLES20.glDisable(GLES20.GL_SCISSOR_TEST); GLES20.glColorMask(true, true, true, true);
        GLES20.glUseProgram(program); GLES20.glActiveTexture(GLES20.GL_TEXTURE0);
        GLES20.glBindTexture(GLES11Ext.GL_TEXTURE_EXTERNAL_OES, texture);
        GLES20.glUniform1i(sampler, 0);
        GLES20.glBindBuffer(GLES20.GL_ARRAY_BUFFER, vertexBuffer);
        GLES20.glBufferSubData(GLES20.GL_ARRAY_BUFFER, 32, 32, uv);
        GLES20.glEnableVertexAttribArray(0); GLES20.glEnableVertexAttribArray(1);
        GLES20.glVertexAttribPointer(0, 2, GLES20.GL_FLOAT, false, 0, 0);
        GLES20.glVertexAttribPointer(1, 2, GLES20.GL_FLOAT, false, 0, 32);
        GLES20.glDrawArrays(GLES20.GL_TRIANGLE_STRIP, 0, 4);
        GLES20.glDisableVertexAttribArray(0); GLES20.glDisableVertexAttribArray(1);
        return true;
    }
    private void release() {
        if (texture != 0) GLES20.glDeleteTextures(1, new int[]{texture}, 0);
        if (vertexBuffer != 0) GLES20.glDeleteBuffers(1, new int[]{vertexBuffer}, 0);
        if (program != 0) GLES20.glDeleteProgram(program);
        texture = 0; program = 0; vertexBuffer = 0;
    }
    @Override public void close() { checkContext(); release(); }
}
