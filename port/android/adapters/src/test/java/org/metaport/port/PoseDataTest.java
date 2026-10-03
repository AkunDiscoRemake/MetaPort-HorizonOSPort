package org.metaport.port;
import org.junit.Test;
import static org.junit.Assert.*;

public class PoseDataTest {
    @Test public void normalizeAndCopy() {
        float[] xyz={1,2,3}; float[] q={0,0,0,2};
        PoseData p=new PoseData(xyz,q);
        xyz[0]=9; q[3]=9;
        assertEquals(1,p.positionMeters()[0],0);
        assertEquals(1,p.quaternionXyzw()[3],0);
        float[] returned=p.positionMeters(); returned[0]=99;
        assertEquals(1,p.positionMeters()[0],0);
    }
    @Test(expected=IllegalArgumentException.class) public void noZeroQuaternion() {
        new PoseData(new float[]{0,0,0},new float[4]);
    }
    @Test(expected=IllegalArgumentException.class) public void noNan() {
        new PoseData(new float[]{Float.NaN,0,0},new float[]{0,0,0,1});
    }
    @Test(expected=IllegalArgumentException.class) public void noWrongShape() {
        new PoseData(new float[2],new float[]{0,0,0,1});
    }
}
