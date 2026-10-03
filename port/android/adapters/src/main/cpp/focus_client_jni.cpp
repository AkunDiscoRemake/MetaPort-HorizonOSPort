// SPDX-License-Identifier: GPL-3.0-only
#include "focus_immersive.hpp"
#include "focus_policy_packet.hpp"
#include <jni.h>
#include <unistd.h>
#include <limits>
#include <memory>

namespace {
using metaport::focus::Client;
using metaport::focus::FocusPolicyCore;
struct Entry {
    const Client identity;
    FocusPolicyCore core;
    int evaluated_types=0;
    metaport::focus::SessionState session;
    jlong session_generation=0;
    explicit Entry(Client client):identity(client) { core.install_client_record(client); }
};
// Opaque, non-reused tokens, not Java-supplied raw pointers. The lock spans each
// core operation so destruction cannot race with lookup. No external callbacks.
std::mutex registry_mutex;
std::map<jlong,std::unique_ptr<Entry>> registry;
jlong last_token=0;
constexpr std::size_t max_clients=32;
void fail(JNIEnv* env,const char* type,const char* message) {
    if (env->ExceptionCheck()) return;
    jclass klass=env->FindClass(type);
    if (klass) { env->ThrowNew(klass,message);env->DeleteLocalRef(klass); }
}
}
extern "C" JNIEXPORT jlong JNICALL
Java_org_metaport_port_focus_NativeFocusClient_nativeCreate(JNIEnv* env,jclass,jint pid,jint uid) {
    // Recheck in native code: Java cannot register an arbitrary process identity.
    if (pid!=getpid() || static_cast<uid_t>(uid)!=getuid()) {
        fail(env,"java/lang/IllegalArgumentException","Only the current native process can be registered");
        return 0;
    }
    try {
        std::lock_guard<std::mutex> lock(registry_mutex);
        if (registry.size()>=max_clients || last_token==std::numeric_limits<jlong>::max()) {
            fail(env,"java/lang/IllegalStateException","Native focus client capacity reached");
            return 0;
        }
        auto entry=std::make_unique<Entry>(Client{uid,pid});
        const jlong token=last_token+1;
        registry.emplace(token,std::move(entry));
        last_token=token;
        return token;
    } catch (const std::bad_alloc&) {
        fail(env,"java/lang/OutOfMemoryError","Native focus allocation failed");
    } catch (const std::exception&) {
        fail(env,"java/lang/IllegalStateException","Native focus registration failed");
    }
    return 0;
}
extern "C" JNIEXPORT jintArray JNICALL
Java_org_metaport_port_focus_NativeFocusClient_nativeIdentity(JNIEnv* env,jclass,jlong token) {
    try {
        std::lock_guard<std::mutex> lock(registry_mutex);
        auto it=registry.find(token);
        if (it==registry.end()) {
            fail(env,"java/lang/IllegalStateException","Unknown or closed native focus client");
            return nullptr;
        }
        const auto& entry=*it->second;
        if (!entry.core.current_focus(entry.identity)) {
            fail(env,"java/lang/IllegalStateException","Native client record absent");
            return nullptr;
        }
        // An installed empty focus set is NOT an observed focus decision. Do not
        // return it as a service status or imply that the policy has evaluated.
        const jint identity[]={entry.identity.pid,entry.identity.uid};
        jintArray result=env->NewIntArray(2);
        if (result) env->SetIntArrayRegion(result,0,2,identity);
        return result;
    } catch (const std::bad_alloc&) {
        fail(env,"java/lang/OutOfMemoryError","Native focus read failed");
    } catch (const std::exception&) {
        fail(env,"java/lang/IllegalStateException","Native focus read failed");
    }
    return nullptr;
}
extern "C" JNIEXPORT void JNICALL
Java_org_metaport_port_focus_NativeFocusClient_nativeDestroy(JNIEnv* env,jclass,jlong token) {
    try {
        std::lock_guard<std::mutex> lock(registry_mutex);
        registry.erase(token); // Idempotent, including stale/unknown tokens.
    } catch (const std::exception&) {
        fail(env,"java/lang/IllegalStateException","Native focus close failed");
    }
}

namespace {
int current_mask(const Entry& entry) {
    const auto state=entry.core.current_focus(entry.identity);
    if (!state) throw std::logic_error("Native client record absent");
    int mask=0;
    for (auto type:*state) mask|=1<<static_cast<int>(type);
    return mask;
}
}
extern "C" JNIEXPORT jbyteArray JNICALL
Java_org_metaport_port_focus_NativeFocusClient_nativeEvaluate(JNIEnv* env,jclass,jlong token,jbyteArray input) {
    using namespace metaport::focus;
    try {
        if (!input) throw std::invalid_argument("Missing focus snapshot");
        const auto size=env->GetArrayLength(input);
        if (size>static_cast<jsize>(packet::max_bytes)) throw std::invalid_argument("Focus snapshot too large");
        std::vector<std::uint8_t> bytes(static_cast<std::size_t>(size));
        if (size) env->GetByteArrayRegion(input,0,size,reinterpret_cast<jbyte*>(bytes.data()));
        if (env->ExceptionCheck()) return nullptr;
        auto request=packet::decode(bytes); // All validation before policy mutation.
        std::lock_guard<std::mutex> lock(registry_mutex);
        auto it=registry.find(token);
        if (it==registry.end()) {
            fail(env,"java/lang/IllegalStateException","Unknown or closed native focus client");
            return nullptr;
        }
        auto& entry=*it->second;
        auto result=entry.core.evaluate(request.type,request.requested,request.immersive,
                                       std::move(request.decisions),request.timestamp);
        for (const auto& row:result.decisions)
            if (row.identity==entry.identity) entry.evaluated_types|=1<<static_cast<int>(row.type);
        auto encoded=packet::encode(result,current_mask(entry),entry.evaluated_types,entry.core.history());
        auto output=env->NewByteArray(static_cast<jsize>(encoded.size()));
        if (output) env->SetByteArrayRegion(output,0,static_cast<jsize>(encoded.size()),
                                           reinterpret_cast<const jbyte*>(encoded.data()));
        return output;
    } catch (const std::invalid_argument&) {
        fail(env,"java/lang/IllegalArgumentException","Invalid focus snapshot");
    } catch (const std::bad_alloc&) {
        fail(env,"java/lang/OutOfMemoryError","Native focus evaluation allocation failed");
    } catch (const std::exception&) {
        fail(env,"java/lang/IllegalStateException","Native focus evaluation failed");
    }
    return nullptr;
}
extern "C" JNIEXPORT jint JNICALL
Java_org_metaport_port_focus_NativeFocusClient_nativeCurrentFocusMask(JNIEnv* env,jclass,jlong token) {
    try {
        std::lock_guard<std::mutex> lock(registry_mutex);
        auto it=registry.find(token);
        if (it==registry.end() || !it->second->evaluated_types) {
            fail(env,"java/lang/IllegalStateException","No evaluated focus state");return 0;
        }
        return current_mask(*it->second);
    } catch (const std::bad_alloc&) {
        fail(env,"java/lang/OutOfMemoryError","Native focus read allocation failed");
    } catch (const std::exception&) {
        fail(env,"java/lang/IllegalStateException","Native focus read failed");
    }
    return 0;
}

namespace {
void fill_session(JNIEnv* env,jlongArray output,const Entry& entry,int effects) {
    const jlong values[]={entry.session_generation,entry.session_generation!=0,
        entry.session.contains(entry.identity),effects,entry.identity.pid,entry.identity.uid};
    env->SetLongArrayRegion(output,0,6,values);
}
}
extern "C" JNIEXPORT jlongArray JNICALL
Java_org_metaport_port_focus_NativeFocusClient_nativeAppState(
        JNIEnv* env,jclass,jlong token,jint caller_pid,jint caller_uid,jint requested_pid,jint state) {
    try {
        // This bridge deliberately supports only its own process. Captured Binder
        // identity is not silently substituted with the server's identity.
        if (caller_pid!=getpid() || static_cast<uid_t>(caller_uid)!=getuid() || requested_pid!=caller_pid) {
            fail(env,"java/lang/SecurityException","Foreign app-state identity is unsupported");return nullptr;
        }
        std::lock_guard<std::mutex> lock(registry_mutex);
        auto it=registry.find(token);
        if (it==registry.end()) {
            fail(env,"java/lang/IllegalStateException","Unknown or closed native focus client");return nullptr;
        }
        auto& entry=*it->second;
        const bool recognized=state==0 || state==2;
        if (recognized && entry.session_generation==std::numeric_limits<jlong>::max()) {
            fail(env,"java/lang/IllegalStateException","App-state generation exhausted");return nullptr;
        }
        auto output=env->NewLongArray(6);if (!output) return nullptr;
        const auto effects=entry.session.apply(caller_pid,requested_pid,static_cast<std::int32_t>(getuid()),state);
        if (effects.access!=metaport::focus::Access::Allowed) {
            fail(env,"java/lang/SecurityException","App-state identity mismatch");return nullptr;
        }
        if (recognized) ++entry.session_generation;
        const int mask=(effects.membership_changed?1:0)|(effects.refresh_activity_state?2:0)
                      |(effects.notify_top_activity?4:0)|(effects.report_immersive_app_update?8:0);
        fill_session(env,output,entry,mask);return output;
    } catch (const std::bad_alloc&) {
        fail(env,"java/lang/OutOfMemoryError","Native app-state allocation failed");
    } catch (const std::exception&) {
        fail(env,"java/lang/IllegalStateException","Native app-state update failed");
    }
    return nullptr;
}
extern "C" JNIEXPORT jlongArray JNICALL
Java_org_metaport_port_focus_NativeFocusClient_nativeAppStateSnapshot(JNIEnv* env,jclass,jlong token) {
    try {
        std::lock_guard<std::mutex> lock(registry_mutex);
        auto it=registry.find(token);
        if (it==registry.end()) {
            fail(env,"java/lang/IllegalStateException","Unknown or closed native focus client");return nullptr;
        }
        auto output=env->NewLongArray(6);
        if (output) fill_session(env,output,*it->second,0);
        return output;
    } catch (const std::bad_alloc&) {
        fail(env,"java/lang/OutOfMemoryError","Native app-state read failed");
    } catch (const std::exception&) {
        fail(env,"java/lang/IllegalStateException","Native app-state read failed");
    }
    return nullptr;
}
