#include "input_router.hpp"
#include <jni.h>
#include <new>

namespace {
metaport::InputRouter* router(jlong handle) {
    return reinterpret_cast<metaport::InputRouter*>(static_cast<uintptr_t>(handle));
}
}
extern "C" JNIEXPORT jlong JNICALL
Java_org_metaport_port_JoyConInput_nativeCreate(JNIEnv*, jclass) {
    return reinterpret_cast<jlong>(new (std::nothrow) metaport::InputRouter());
}
extern "C" JNIEXPORT void JNICALL
Java_org_metaport_port_JoyConInput_nativeDestroy(JNIEnv*, jclass, jlong h) { delete router(h); }
extern "C" JNIEXPORT jboolean JNICALL
Java_org_metaport_port_JoyConInput_nativeConnect(JNIEnv*, jclass, jlong h, jint id, jint side) {
    return h && router(h)->connect(id,side);
}
extern "C" JNIEXPORT void JNICALL
Java_org_metaport_port_JoyConInput_nativeDisconnect(JNIEnv*, jclass, jlong h, jint id) {
    if (h) router(h)->disconnect(id);
}
extern "C" JNIEXPORT void JNICALL
Java_org_metaport_port_JoyConInput_nativeReset(JNIEnv*, jclass, jlong h) { if(h) router(h)->reset(); }
extern "C" JNIEXPORT jboolean JNICALL
Java_org_metaport_port_JoyConInput_nativeKey(JNIEnv*, jclass, jlong h, jint id, jint button, jboolean down, jlong time) {
    return h && router(h)->key(id,static_cast<uint32_t>(button),down,time);
}
extern "C" JNIEXPORT jboolean JNICALL
Java_org_metaport_port_JoyConInput_nativeAxis(JNIEnv*, jclass, jlong h, jint id, jfloat x, jfloat y, jlong time) {
    return h && router(h)->axis(id,x,y,time);
}
extern "C" JNIEXPORT void JNICALL
Java_org_metaport_port_JoyConInput_nativeRead(JNIEnv* env, jclass, jlong h, jlongArray meta, jfloatArray axes) {
    if (!h || !meta || !axes || env->GetArrayLength(meta)!=14 || env->GetArrayLength(axes)!=4) return;
    const auto s=router(h)->drain();const auto &l=s.controllers[0];const auto &r=s.controllers[1];
    const jlong m[]={static_cast<jlong>(s.mode),l.device_id,r.device_id,l.buttons,r.buttons,
        l.event_time_ns,r.event_time_ns,l.stick_valid,r.stick_valid,s.original_hand_provider_connected,l.pressed,r.pressed,l.released,r.released};
    const jfloat a[]={l.stick_x,l.stick_y,r.stick_x,r.stick_y};
    env->SetLongArrayRegion(meta,0,14,m);
    env->SetFloatArrayRegion(axes,0,4,a);
}
