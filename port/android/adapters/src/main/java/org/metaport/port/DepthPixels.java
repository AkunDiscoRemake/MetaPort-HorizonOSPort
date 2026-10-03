// SPDX-License-Identifier: GPL-3.0-only
package org.metaport.port;

import java.nio.ByteBuffer;

/** Reads Android/ARCore unsigned little-endian depth millimeters, not a Quest ABI.
 * Zero means no depth observation. Coordinates are depth-image pixels, NOT screen
 * or eye coordinates; projection/calibration belongs to the caller.
 */
public final class DepthPixels {
    private DepthPixels() {}
    public static int millimeters(ByteBuffer bytes, int width, int height,
                                  int rowStride, int pixelStride, int x, int y) {
        int offset = offset(bytes, width, height, rowStride, pixelStride, x, y, 2);
        return (bytes.get(offset) & 255) | ((bytes.get(offset + 1) & 255) << 8);
    }
    public static int confidence(ByteBuffer bytes, int width, int height,
                                 int rowStride, int pixelStride, int x, int y) {
        return bytes.get(offset(bytes, width, height, rowStride, pixelStride, x, y, 1)) & 255;
    }
    private static int offset(ByteBuffer b, int w, int h, int row, int pixel,
                              int x, int y, int sampleBytes) {
        if (w <= 0 || h <= 0 || x < 0 || y < 0 || x >= w || y >= h ||
                pixel < sampleBytes || row < (long)(w - 1) * pixel + sampleBytes)
            throw new IllegalArgumentException("Invalid depth layout or pixel");
        long offset = b.position() + (long)y * row + (long)x * pixel;
        if (offset + sampleBytes > b.limit()) throw new IllegalArgumentException("Truncated depth plane");
        return (int)offset;
    }
}
