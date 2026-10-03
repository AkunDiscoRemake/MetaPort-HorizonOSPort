// SPDX-License-Identifier: GPL-3.0-only
#include "focus_immersive.hpp"
#include "focus_policy_packet.hpp"
#include "focus_session_binding.hpp"
#include "focus_window_observation.hpp"
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
    metaport::focus::WindowObservation window;
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
namespace {
jbyteArray evaluate_packet(JNIEnv* env,jlong token,jbyteArray input,bool session_bound,bool window_bound,
                           jlong source_token,jlong generation,jlong window_source,jlong window_generation) {
    using namespace metaport::focus;
    try {
        if (!input) throw std::invalid_argument("Missing focus snapshot");
        const auto size=env->GetArrayLength(input);
        if (size>static_cast<jsize>(packet::max_bytes)) throw std::invalid_argument("Focus snapshot too large");
        std::vector<std::uint8_t> bytes(static_cast<std::size_t>(size));
        if (size) env->GetByteArrayRegion(input,0,size,reinterpret_cast<jbyte*>(bytes.data()));
        if (env->ExceptionCheck()) return nullptr;
        auto request=packet::decode(bytes); // All validation before policy mutation.
        packet::require(request.session_rendering==session_bound && request.observed_window==window_bound);
        std::lock_guard<std::mutex> lock(registry_mutex);
        auto it=registry.find(token);
        if (it==registry.end()) {
            fail(env,"java/lang/IllegalStateException","Unknown or closed native focus client");
            return nullptr;
        }
        auto& entry=*it->second;
        if (session_bound) {
            packet::require(source_token==token);
            if (generation<=0 || generation!=entry.session_generation) {
                fail(env,"java/lang/IllegalStateException","Stale or unavailable session observation");
                return nullptr;
            }
            bind_own_session_rendering(request,entry.identity,entry.session.contains(entry.identity));
        }
        if (window_bound) {
            packet::require(!request.decisions.window_focus);
            if (!entry.window.matches(window_source,window_generation)) {
                fail(env,"java/lang/IllegalStateException","Stale or unavailable window observation");return nullptr;
            }
            // Positive evidence for this process only. No display-focus inference.
            request.decisions.window_focus=entry.identity;
        }
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
} // namespace
extern "C" JNIEXPORT jbyteArray JNICALL
Java_org_metaport_port_focus_NativeFocusClient_nativeEvaluate(JNIEnv* env,jclass,jlong token,jbyteArray input) {
    return evaluate_packet(env,token,input,false,false,0,0,0,0);
}
extern "C" JNIEXPORT jbyteArray JNICALL
Java_org_metaport_port_focus_NativeFocusClient_nativeEvaluateSession(
        JNIEnv* env,jclass,jlong token,jlong source_token,jlong generation,jbyteArray input) {
    return evaluate_packet(env,token,input,true,false,source_token,generation,0,0);
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

extern "C" JNIEXPORT jbyteArray JNICALL
Java_org_metaport_port_focus_NativeFocusClient_nativeEvaluateObserved(
        JNIEnv* env,jclass,jlong token,jlong source_token,jlong generation,
        jlong window_source,jlong window_generation,jbyteArray input) {
    return evaluate_packet(env,token,input,true,true,source_token,generation,window_source,window_generation);
}
extern "C" JNIEXPORT jlong JNICALL
Java_org_metaport_port_focus_NativeFocusClient_nativeAttachWindow(JNIEnv* env,jclass,jlong token) {
    try {
        std::lock_guard<std::mutex> lock(registry_mutex);
        auto it=registry.find(token);
        if (it==registry.end()) throw std::logic_error("Closed client");
        return it->second->window.attach();
    } catch (const std::exception&) {
        fail(env,"java/lang/IllegalStateException","Cannot attach native window source");
    }
    return 0;
}
extern "C" JNIEXPORT jlongArray JNICALL
Java_org_metaport_port_focus_NativeFocusClient_nativeObserveWindow(
        JNIEnv* env,jclass,jlong token,jlong source,jboolean positive) {
    try {
        std::lock_guard<std::mutex> lock(registry_mutex);
        auto it=registry.find(token);
        if (it==registry.end()) throw std::logic_error("Closed client");
        auto output=env->NewLongArray(3);if (!output) return nullptr;
        auto& window=it->second->window;window.observe(source,positive==JNI_TRUE);
        const jlong values[]={window.source(),window.generation(),window.known()};
        env->SetLongArrayRegion(output,0,3,values);return output;
    } catch (const std::exception&) {
        fail(env,"java/lang/IllegalStateException","Cannot update native window source");
    }
    return nullptr;
}
extern "C" JNIEXPORT void JNICALL
Java_org_metaport_port_focus_NativeFocusClient_nativeDetachWindow(JNIEnv* env,jclass,jlong token,jlong source) {
    try {
        std::lock_guard<std::mutex> lock(registry_mutex);
        auto it=registry.find(token);
        if (it!=registry.end()) it->second->window.detach(source);
    } catch (const std::exception&) {
        fail(env,"java/lang/IllegalStateException","Cannot detach native window source");
    }
}
