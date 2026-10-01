package org.metaport.port;
import org.junit.Test;
import java.nio.ByteBuffer;
import java.nio.ByteOrder;
import static org.junit.Assert.*;

public final class DepthPixelsTest {
    @Test public void readsUnsignedLittleEndianWithPaddingAndNonzeroPosition() {
        ByteBuffer b=ByteBuffer.allocate(32).order(ByteOrder.BIG_ENDIAN);
        b.position(3); b.put(3,(byte)0xff); b.put(4,(byte)0xff);
        b.put(19,(byte)0x34); b.put(20,(byte)0x12);
        assertEquals(65535, DepthPixels.millimeters(b,2,2,12,4,0,0));
        assertEquals(0x1234, DepthPixels.millimeters(b,2,2,12,4,1,1));
        assertEquals(3,b.position());
    }
    @Test public void zeroIsMissingNotInventedDistance() {
        assertEquals(0,DepthPixels.millimeters(ByteBuffer.allocate(2),1,1,2,2,0,0));
        assertEquals(255,DepthPixels.confidence(ByteBuffer.wrap(new byte[]{(byte)255}),1,1,1,1,0,0));
    }
    @Test(expected=IllegalArgumentException.class) public void rejectsTruncatedPlane() {
        DepthPixels.millimeters(ByteBuffer.allocate(1),1,1,2,2,0,0);
    }
    @Test(expected=IllegalArgumentException.class) public void rejectsOverlappingRows() {
        DepthPixels.millimeters(ByteBuffer.allocate(16),2,2,2,2,1,1);
    }
    @Test(expected=IllegalArgumentException.class) public void rejectsOutOfBounds() {
        DepthPixels.millimeters(ByteBuffer.allocate(4),1,1,2,2,1,0);
    }
    @Test(expected=IllegalArgumentException.class) public void rejectsOverflowingOffset() {
        DepthPixels.millimeters(ByteBuffer.allocate(4),1,Integer.MAX_VALUE,Integer.MAX_VALUE,2,0,Integer.MAX_VALUE-1);
    }
}
