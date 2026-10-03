// SPDX-License-Identifier: GPL-3.0-only
package org.metaport.port.focus.protocol;

import android.os.Binder;
import android.os.DeadObjectException;
import android.os.IBinder;
import android.os.RemoteException;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.List;
import java.util.NoSuchElementException;
import java.util.Objects;

/** Listener ownership only: no focus policy, initial event, tracking grant or publication.
 * Call registration on the original Binder thread, after endpoint decoding.
 * Dispatch actual policy changes on a service worker, never the UI thread.
 */
public final class FocusListeners implements AutoCloseable {
    public interface AccessPolicy { void enforce(int pid, int uid, int transaction); }
    public static final class Delivery {
        public final int sent, failed, skipped;
        private Delivery(int sent,int failed,int skipped) { this.sent=sent;this.failed=failed;this.skipped=skipped; }
    }
    private static final int TOP=-1, LIMIT=256, OWNER_LIMIT=64;
    private final Object lock=new Object();
    private final AccessPolicy access;
    private final List<Entry> entries=new ArrayList<>();
    private boolean closed;
    private final class Entry implements IBinder.DeathRecipient {
        final int pid,uid,channel;
        final IBinder binder;
        boolean active;
        Entry(int pid,int uid,int channel,IBinder binder) {
            this.pid=pid;this.uid=uid;this.channel=channel;this.binder=binder;
        }
        @Override public void binderDied() { removeBinder(binder); }
    }
    public FocusListeners(AccessPolicy access) { this.access=Objects.requireNonNull(access); }
    private static void focusType(int type) {
        if (type!=0 && type!=1) throw new IllegalArgumentException("Invalid original focus type");
    }
    private void open() { if (closed) throw new IllegalStateException("Focus listeners closed"); }
    public boolean registerTop(IBinder binder) { return register(TOP,binder,4); }
    public boolean registerFocus(IBinder binder,int type) { return register(type,binder,2); }
    private boolean register(int channel,IBinder binder,int transaction) {
        int pid=Binder.getCallingPid(),uid=Binder.getCallingUid();
        access.enforce(pid,uid,transaction);
        if (transaction==2) focusType(channel);
        Objects.requireNonNull(binder);
        Entry entry=new Entry(pid,uid,channel,binder);
        synchronized(lock) {
            open(); int own=0;
            for (Entry old:entries) if (old.pid==pid && old.channel==channel) {
                if (old.uid!=uid) throw new SecurityException("PID owner changed");
                own++;
            }
            if (entries.size()>=LIMIT || own>=OWNER_LIMIT) throw new IllegalStateException("Focus listener budget");
            entries.add(entry); // Reserve capacity before linking, but not eligible for delivery.
        }
        boolean linked=false,accepted=false;
        try {
            binder.linkToDeath(entry,0); linked=true;
            boolean alive=binder.isBinderAlive();
            synchronized(lock) {
                if (!closed && alive && entries.contains(entry)) { entry.active=true;accepted=true; }
            }
            return accepted;
        } catch (RemoteException dead) { return false; }
        finally {
            if (!accepted) {
                synchronized(lock) { entry.active=false;entries.remove(entry); }
                if (linked) unlink(entry);
            }
        }
    }
    public boolean unregisterTop() { return unregister(TOP,5); }
    public boolean unregisterFocus(int type) { return unregister(type,3); }
    private boolean unregister(int channel,int transaction) {
        int pid=Binder.getCallingPid(),uid=Binder.getCallingUid();
        access.enforce(pid,uid,transaction);
        if (transaction==3) focusType(channel);
        List<Entry> removed=new ArrayList<>();
        synchronized(lock) {
            open();
            for (Entry entry:entries) if (entry.channel==channel && entry.pid==pid) {
                if (entry.uid!=uid) throw new SecurityException("PID owner changed");
                removed.add(entry);
            }
            if (removed.isEmpty()) throw new IllegalArgumentException("No listeners for calling PID");
            for (Entry entry:removed) entry.active=false;
            entries.removeAll(removed);
        }
        for (Entry entry:removed) unlink(entry);
        return true;
    }
    private static void unlink(Entry entry) {
        try { entry.binder.unlinkToDeath(entry,0); }
        catch (NoSuchElementException alreadyGone) { /* Death or registration/link race. */ }
    }
    private void removeBinder(IBinder binder) {
        List<Entry> removed=new ArrayList<>();
        synchronized(lock) {
            for (Entry entry:entries) if (entry.binder==binder) { entry.active=false;removed.add(entry); }
            entries.removeAll(removed);
        }
        for (Entry entry:removed) unlink(entry);
    }
    public int size() {
        synchronized(lock) { int count=0;for (Entry entry:entries) if (entry.active) count++;return count; }
    }
    private List<Entry> snapshot(boolean top) {
        synchronized(lock) {
            open(); List<Entry> result=new ArrayList<>();
            for (Entry entry:entries) if (entry.active && (entry.channel==TOP)==top) result.add(entry);
            // Original: signed type/PID map order, insertion order within a PID vector.
            result.sort(Comparator.comparingInt((Entry e)->e.channel).thenComparingInt(e->e.pid));
            return result;
        }
    }
    /** Original callback carries the changed focus TYPE, not a boolean/granted pose. */
    public Delivery notifyFocusChanged() { return dispatch(false,null,null); }
    public Delivery notifyTopChanged(String top,FocusWire.ImmersiveApp immersive) {
        Objects.requireNonNull(immersive);return dispatch(true,top,immersive);
    }
    private Delivery dispatch(boolean top,String activity,FocusWire.ImmersiveApp immersive) {
        int sent=0,failed=0,skipped=0;
        for (Entry entry:snapshot(top)) {
            synchronized(lock) {
                if (!entry.active || closed) { skipped++;continue; }
            }
            // No registry lock across application/Binder code. An admitted delivery may
            // finish after unregister; later snapshot entries are cancelled by active=false.
            try {
                if (top) FocusWire.notifyTopActivity(entry.binder,activity,immersive);
                else FocusWire.notifyFocus(entry.binder,entry.channel);
                sent++;
            } catch (DeadObjectException dead) { failed++;removeBinder(entry.binder); }
            catch (RemoteException | RuntimeException recipientFailure) { failed++; }
        }
        return new Delivery(sent,failed,skipped);
    }
    @Override public void close() {
        List<Entry> removed;
        synchronized(lock) {
            if (closed) return;
            closed=true;removed=new ArrayList<>(entries);entries.clear();
            for (Entry entry:removed) entry.active=false;
        }
        for (Entry entry:removed) unlink(entry);
    }
}
