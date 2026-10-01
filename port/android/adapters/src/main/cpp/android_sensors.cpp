#include "sample_cache.hpp"
#include <android/looper.h>
#include <android/sensor.h>
#include <jni.h>
#include <atomic>
#include <future>
#include <memory>
#include <exception>
#include <string>
#include <thread>

namespace {
// Queue cleanup must run on its owning sensor thread, including initialization errors.
struct QueueOwner {
    ASensorManager* manager=nullptr;
    ASensorEventQueue* queue=nullptr;
    const ASensor* enabled[3]{};
    ~QueueOwner() {
        if (!queue) return;
        for (const ASensor* value:enabled)
            if (value) ASensorEventQueue_disableSensor(queue,value);
        ASensorManager_destroyEventQueue(manager,queue);
    }
};
class Sensors {
public:
    explicit Sensors(std::string package) : package_(std::move(package)) {}
    ~Sensors() { stop(); }
    int start(int period_us) {
        stop();
        cache.reset();
        stop_ = false;
        std::promise<int> ready;
        auto future = ready.get_future();
        thread_ = std::thread([this, period_us, signal=std::move(ready)]() mutable {
            bool reported=false;
            try {
            QueueOwner owner;
            ASensorManager* manager = ASensorManager_getInstanceForPackage(package_.c_str());
            ALooper* looper = ALooper_prepare(ALOOPER_PREPARE_ALLOW_NON_CALLBACKS);
            if (!manager || !looper) { signal.set_value(-1); return; }
            ASensorEventQueue* queue = ASensorManager_createEventQueue(manager, looper, 1, nullptr, nullptr);
            if (!queue) { signal.set_value(-2); return; }
            owner.manager=manager; owner.queue=queue;
            const int types[] = {ASENSOR_TYPE_GAME_ROTATION_VECTOR, ASENSOR_TYPE_GYROSCOPE, ASENSOR_TYPE_ACCELEROMETER};
            const ASensor* sensors[3]{};
            int mask = 0;
            for (int i=0; i<3; ++i) {
                sensors[i] = ASensorManager_getDefaultSensor(manager, types[i]);
                if (sensors[i] && ASensorEventQueue_enableSensor(queue, sensors[i]) == 0) {
                    if (ASensorEventQueue_setEventRate(queue, sensors[i], period_us) == 0) {
                        mask |= (1 << i); owner.enabled[i]=sensors[i];
                    }
                    else ASensorEventQueue_disableSensor(queue, sensors[i]);
                }
            }
            active_mask = mask;
            signal.set_value(mask);
            reported=true;
            while (mask != 0 && !stop_) {
                const int event = ALooper_pollOnce(50, nullptr, nullptr, nullptr);
                if (event == ALOOPER_POLL_ERROR) break;
                ASensorEvent batch[16];
                ssize_t count;
                while (!stop_ && (count = ASensorEventQueue_getEvents(queue, batch, 16)) > 0) {
                    for (ssize_t j=0; j<count; ++j) {
                        const auto& e=batch[j];
                        for (int i=0; i<3; ++i) if (e.type == types[i] && (mask & (1 << i))) {
                            // Android rotation vector supplies xyzw; no invented translation.
                            const std::array<float,4> v = {e.data[0], e.data[1], e.data[2], i==0 ? e.data[3] : 0.0f};
                            const int accuracy = i==0 ? -1 : e.vector.status;
                            cache.put(static_cast<metaport::SampleCache::Kind>(i), e.timestamp, v, accuracy);
                        }
                    }
                }
            }
            } catch (...) {
                // Never allow a worker exception to call std::terminate. An initialization
                // exception crosses future.get() and is translated at the JNI boundary.
                if (!reported) signal.set_exception(std::current_exception());
            }
            active_mask = 0;
            cache.reset();
        });
        return future.get();
    }
    void stop() {
        stop_ = true;
        if (thread_.joinable()) thread_.join();
        active_mask = 0;
        cache.reset();
    }
    std::atomic<int> active_mask{0};
    metaport::SampleCache cache;
private:
    std::string package_;
    std::atomic<bool> stop_{true};
    std::thread thread_;
};
void javaError(JNIEnv* env,const char* type,const char* message) {
    if (env->ExceptionCheck()) return;
    jclass cls=env->FindClass(type);
    if (cls) { env->ThrowNew(cls,message); env->DeleteLocalRef(cls); }
}
class UtfChars {
    JNIEnv* env_; jstring value_;
public:
    const char* data;
    UtfChars(JNIEnv* env,jstring value):env_(env),value_(value),data(env->GetStringUTFChars(value,nullptr)) {}
    ~UtfChars() { if(data) env_->ReleaseStringUTFChars(value_,data); }
};
Sensors* sensor(jlong handle) { return reinterpret_cast<Sensors*>(handle); }
}
extern "C" JNIEXPORT jlong JNICALL Java_org_metaport_port_NativeSensors_nativeCreate(JNIEnv* env,jclass,jstring name) {
    if (!name) { javaError(env,"java/lang/IllegalArgumentException","Missing package name"); return 0; }
    try {
        UtfChars raw(env,name);
        if (!raw.data) return 0;
        return reinterpret_cast<jlong>(new Sensors(std::string(raw.data)));
    } catch (const std::bad_alloc& e) {
        javaError(env,"java/lang/OutOfMemoryError",e.what()); return 0;
    } catch (const std::exception& e) {
        javaError(env,"java/lang/IllegalStateException",e.what()); return 0;
    }
}
extern "C" JNIEXPORT jint JNICALL Java_org_metaport_port_NativeSensors_nativeStart(JNIEnv* env,jclass,jlong h,jint period) {
    try { return sensor(h)->start(period); }
    catch (const std::exception& e) { javaError(env,"java/lang/IllegalStateException",e.what()); return -3; }
}
extern "C" JNIEXPORT void JNICALL Java_org_metaport_port_NativeSensors_nativeStop(JNIEnv*,jclass,jlong h) { sensor(h)->stop(); }
extern "C" JNIEXPORT void JNICALL Java_org_metaport_port_NativeSensors_nativeDestroy(JNIEnv*,jclass,jlong h) { delete sensor(h); }
extern "C" JNIEXPORT jint JNICALL Java_org_metaport_port_NativeSensors_nativeRead(JNIEnv* env,jclass,jlong h,jlong now,jlong age,jlongArray meta,jfloatArray values) {
    if (!meta || !values || env->GetArrayLength(meta)!=9 || env->GetArrayLength(values)!=12) {
        javaError(env,"java/lang/IllegalArgumentException","Invalid sensor output arrays"); return 0;
    }
    const auto samples=sensor(h)->cache.read(now,age);
    const int mask = sensor(h)->active_mask.load();
    jlong m[9]{}; jfloat v[12]{};
    for (int i=0;i<3;++i) {
        m[3*i]=samples[i].timestamp_ns; m[3*i+1]=samples[i].accuracy; m[3*i+2]=samples[i].observed && (mask & (1 << i));
        for (int j=0;j<4;++j) v[4*i+j]=samples[i].value[j];
    }
    env->SetLongArrayRegion(meta,0,9,m);
    if (!env->ExceptionCheck()) env->SetFloatArrayRegion(values,0,12,v);
    return mask;
}
