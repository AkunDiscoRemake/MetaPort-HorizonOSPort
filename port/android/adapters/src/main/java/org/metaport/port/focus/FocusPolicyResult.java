// SPDX-License-Identifier: GPL-3.0-only
package org.metaport.port.focus;

import java.nio.ByteBuffer;
import java.nio.ByteOrder;
import java.nio.charset.CharacterCodingException;
import java.nio.charset.CodingErrorAction;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.Collections;
import java.util.List;

/** Native decision result for an explicitly supplied snapshot, not an OS grant. */
final class FocusPolicyResult {
    static final class App {
        final int uid,pid;final String packageName;final boolean top;
        App(int uid,int pid,String name,boolean top) { this.uid=uid;this.pid=pid;packageName=name;this.top=top; }
    }
    static final class Decision {
        final int uid,pid,type;final boolean focused;
        Decision(int uid,int pid,int type,boolean focused) { this.uid=uid;this.pid=pid;this.type=type;this.focused=focused; }
    }
    static final class History {
        final long epochMillis;final App app;
        History(long time,App app) { epochMillis=time;this.app=app; }
    }
    final String topActivity;
    final App immersive;
    final List<Decision> decisions;
    final int registeredClientFocusMask;
    final List<History> history;
    private FocusPolicyResult(ByteBuffer in) {
        require(in.getInt()==0x3152504d);
        topActivity=text(in);immersive=bool(in)?app(in):null;
        int count=count(in,256);List<Decision> rows=new ArrayList<>();
        for (int i=0;i<count;i++) {
            int uid=in.getInt(),pid=in.getInt(),type=in.getInt();require(type==0 || type==1);
            rows.add(new Decision(uid,pid,type,bool(in)));
        }
        decisions=Collections.unmodifiableList(rows);
        registeredClientFocusMask=in.getInt();require(registeredClientFocusMask>=0 && registeredClientFocusMask<=3);
        count=count(in,10);List<History> entries=new ArrayList<>();
        for (int i=0;i<count;i++) {
            long time=in.getLong();require(time>=0 && time<=9223372036854L);
            entries.add(new History(time,app(in)));
        }
        history=Collections.unmodifiableList(entries);require(!in.hasRemaining());
    }
    static FocusPolicyResult decode(byte[] bytes) {
        try {
            require(bytes!=null && bytes.length<=65536);
            return new FocusPolicyResult(ByteBuffer.wrap(bytes).order(ByteOrder.LITTLE_ENDIAN));
        } catch (RuntimeException error) { throw new IllegalStateException("Invalid native focus result",error); }
    }
    private static void require(boolean valid) { if (!valid) throw new IllegalArgumentException("Invalid result"); }
    private static int count(ByteBuffer in,int cap) { int size=in.getInt();require(size>=0 && size<=cap);return size; }
    private static boolean bool(ByteBuffer in) { int value=in.getInt();require(value==0 || value==1);return value==1; }
    private static App app(ByteBuffer in) { int uid=in.getInt(),pid=in.getInt();String name=text(in);return new App(uid,pid,name,bool(in)); }
    private static String text(ByteBuffer in) {
        int size=count(in,1024);require(size<=in.remaining());
        ByteBuffer data=in.slice();data.limit(size);in.position(in.position()+size);
        try { return StandardCharsets.UTF_8.newDecoder().onMalformedInput(CodingErrorAction.REPORT)
                .onUnmappableCharacter(CodingErrorAction.REPORT).decode(data).toString(); }
        catch (CharacterCodingException error) { throw new IllegalArgumentException("Invalid UTF-8 result",error); }
    }
}
