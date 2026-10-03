package org.metaport.port;
import org.junit.Test;
import static org.junit.Assert.*;

public class JoyConProtocolTest {
    @Test public void identityIsExplicitNotNameBased() {
        assertEquals(0,JoyConProtocol.side(0x057e,0x2006));
        assertEquals(1,JoyConProtocol.side(0x057e,0x2007));
        assertEquals(-1,JoyConProtocol.side(0x057e,0x2009));
        assertEquals(-1,JoyConProtocol.side(0,0x2006));
        assertEquals(-1,JoyConProtocol.side(0x057e,0));
    }
    @Test public void centeredAndUnsignedAxes() {
        assertEquals(0,JoyConProtocol.normalizeStick(.1f,-1,1,.2f),0);
        assertEquals(.5f,JoyConProtocol.normalizeStick(.6f,-1,1,.2f),.00001f);
        assertEquals(-1,JoyConProtocol.normalizeStick(0,0,255,5),0);
        assertEquals(1,JoyConProtocol.normalizeStick(255,0,255,5),0);
        assertEquals(0,JoyConProtocol.normalizeStick(127.5f,0,255,5),0);
        assertEquals(1,JoyConProtocol.normalizeStick(2,-1,1,0),0);
    }
    @Test public void invalidRangesNeverYieldFakeValidInput() {
        for (float[] a: new float[][]{{Float.NaN,-1,1,0},{0,1,1,0},{0,1,-1,0},
                {0,-1,1,1},{0,-1,1,-.1f},{Float.POSITIVE_INFINITY,-1,1,0}}) {
            try { JoyConProtocol.normalizeStick(a[0],a[1],a[2],a[3]);fail("accepted bad axis"); }
            catch(IllegalArgumentException expected) { }
        }
    }
}
