// SPDX-License-Identifier: GPL-3.0-only
package org.metaport.port.focus;

import java.nio.ByteBuffer;
import java.nio.ByteOrder;
import java.nio.CharBuffer;
import java.nio.BufferOverflowException;
import java.nio.charset.CharacterCodingException;
import java.nio.charset.CodingErrorAction;
import java.nio.charset.StandardCharsets;
import java.util.Arrays;
import java.util.Objects;

/** Internal complete, trusted snapshot. NOT Binder arguments or a permission API.
 * Every channel must be supplied, including known-empty feeds. No Android producer
 * yet supplies all channels. Never fill missing observations with empty arrays.
 * Names/permission masks require resolved metadata, not raw caller claims or wishes.
 * Package-private until that producer is integrated; instrumentation uses fixtures.
 */
final class FocusPolicyFrame {
    static final int MAX_BYTES=65536, MAX_ROWS=256, MAX_TEXT=1024;
    static final class Client {
        final int uid,pid;
        Client(int uid,int pid) { this.uid=uid;this.pid=pid; }
    }
    static final class Request {
        final Client identity;final int backgroundAccessMask;
        Request(Client identity,int mask) { this.identity=Objects.requireNonNull(identity);backgroundAccessMask=mask; }
    }
    static final class Metadata {
        final Client identity;
        final String packageName,metadataProcessName,processNameForTop;
        Metadata(Client identity,String packageName,String metadataProcessName,String processNameForTop) {
            this.identity=Objects.requireNonNull(identity);
            this.packageName=Objects.requireNonNull(packageName);
            this.metadataProcessName=Objects.requireNonNull(metadataProcessName);
            this.processNameForTop=Objects.requireNonNull(processNameForTop);
        }
    }
    private final byte[] packet;
    FocusPolicyFrame(int type,long observedEpochMillis,Request[] requested,
                     Client[] activities,Client[] panels,Client[] topClients,Client[] allTopClients,
                     Client window,boolean mainDisplayFocus,Metadata[] rendering,Metadata[] liveMetadata,
                     Metadata[] foregroundLookups,String primaryDisplayTop) {
        this(type,observedEpochMillis,requested,activities,panels,topClients,allTopClients,window,
                mainDisplayFocus,rendering,liveMetadata,foregroundLookups,primaryDisplayTop,0);
    }
    // Rendering is delegated, not asserted empty. A distinct wire tag prevents this
    // packet from being accidentally evaluated through the unbound fixture path.
    static FocusPolicyFrame forSession(int type,long observedEpochMillis,Request[] requested,
                     Client[] activities,Client[] panels,Client[] topClients,Client[] allTopClients,
                     Client window,boolean mainDisplayFocus,Metadata[] liveMetadata,
                     Metadata[] foregroundLookups,String primaryDisplayTop) {
        return new FocusPolicyFrame(type,observedEpochMillis,requested,activities,panels,topClients,
                allTopClients,window,mainDisplayFocus,new Metadata[0],liveMetadata,
                foregroundLookups,primaryDisplayTop,1);
    }
    static FocusPolicyFrame forObservedInputs(int type,long observedEpochMillis,Request[] requested,
                     Client[] activities,Client[] panels,Client[] topClients,Client[] allTopClients,
                     boolean mainDisplayFocus,Metadata[] liveMetadata,Metadata[] foregroundLookups,String primaryDisplayTop) {
        return new FocusPolicyFrame(type,observedEpochMillis,requested,activities,panels,topClients,
                allTopClients,null,mainDisplayFocus,new Metadata[0],liveMetadata,foregroundLookups,primaryDisplayTop,2);
    }
    private FocusPolicyFrame(int type,long observedEpochMillis,Request[] requested,
                     Client[] activities,Client[] panels,Client[] topClients,Client[] allTopClients,
                     Client window,boolean mainDisplayFocus,Metadata[] rendering,Metadata[] liveMetadata,
                     Metadata[] foregroundLookups,String primaryDisplayTop,int binding) {
        if (type<0 || type>1 || observedEpochMillis<0 || observedEpochMillis>9223372036854L)
            throw new IllegalArgumentException("Invalid type or observation timestamp");
        ByteBuffer out=ByteBuffer.allocate(MAX_BYTES).order(ByteOrder.LITTLE_ENDIAN);
        try {
            out.putInt(binding==2?0x4f46504d:binding==1?0x5346504d:0x3146504d).putInt(type).putLong(observedEpochMillis);
            count(out,Objects.requireNonNull(requested).length);
            for (Request row:requested) {
                Objects.requireNonNull(row);
                if (row.backgroundAccessMask<0 || row.backgroundAccessMask>3)
                    throw new IllegalArgumentException("Invalid resolved background-access mask");
                identity(out,row.identity);out.putInt(row.backgroundAccessMask);
            }
            identities(out,activities);identities(out,panels);identities(out,topClients);identities(out,allTopClients);
            out.putInt(window==null?0:1);if (window!=null) identity(out,window);
            out.putInt(mainDisplayFocus?1:0);
            metadataList(out,rendering);metadataList(out,liveMetadata);
            count(out,Objects.requireNonNull(foregroundLookups).length);
            for (Metadata row:foregroundLookups) {
                out.putInt(row==null?0:1);if (row!=null) metadata(out,row);
            }
            text(out,primaryDisplayTop);
            packet=Arrays.copyOf(out.array(),out.position());
        } catch (BufferOverflowException error) {
            throw new IllegalArgumentException("Focus snapshot exceeds byte budget",error);
        }
    }
    byte[] encode() { return packet.clone(); }
    private static void count(ByteBuffer out,int size) {
        if (size<0 || size>MAX_ROWS) throw new IllegalArgumentException("Focus row budget exceeded");
        out.putInt(size);
    }
    private static void identity(ByteBuffer out,Client value) {
        Objects.requireNonNull(value);out.putInt(value.uid).putInt(value.pid);
    }
    private static void identities(ByteBuffer out,Client[] values) {
        count(out,Objects.requireNonNull(values).length);
        for (Client value:values) identity(out,value);
    }
    private static void metadataList(ByteBuffer out,Metadata[] values) {
        count(out,Objects.requireNonNull(values).length);
        for (Metadata value:values) metadata(out,value);
    }
    private static void metadata(ByteBuffer out,Metadata value) {
        Objects.requireNonNull(value);identity(out,value.identity);text(out,value.packageName);
        text(out,value.metadataProcessName);text(out,value.processNameForTop);
    }
    private static void text(ByteBuffer out,String value) {
        Objects.requireNonNull(value);
        if (value.length()>MAX_TEXT) throw new IllegalArgumentException("Text budget exceeded");
        try {
            ByteBuffer utf8=StandardCharsets.UTF_8.newEncoder().onMalformedInput(CodingErrorAction.REPORT)
                    .onUnmappableCharacter(CodingErrorAction.REPORT).encode(CharBuffer.wrap(value));
            if (utf8.remaining()>MAX_TEXT) throw new IllegalArgumentException("UTF-8 budget exceeded");
            out.putInt(utf8.remaining());out.put(utf8);
        } catch (CharacterCodingException error) {
            throw new IllegalArgumentException("Invalid UTF-16 input",error);
        }
    }
}
