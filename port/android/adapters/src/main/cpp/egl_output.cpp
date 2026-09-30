#include <jni.h>
#include <android/native_window.h>
#include <android/native_window_jni.h>
#include <EGL/egl.h>
#include <EGL/eglext.h>
#include <cstring>
#include <memory>
#include <stdexcept>
#include <string>

namespace {
void require(bool condition, const char* message) {
    if (!condition) throw std::runtime_error(std::string(message) + " (EGL " + std::to_string(eglGetError()) + ")");
}
bool extension(const char* list, const char* wanted) {
    if (!list) return false;
    const size_t length=std::strlen(wanted);
    const char* at=list;
    while ((at=std::strstr(at,wanted))) {
        if ((at==list || at[-1]==' ') && (at[length]==' ' || at[length]=='\0')) return true;
        at+=length;
    }
    return false;
}
class Output {
public:
    EGLDisplay display=EGL_NO_DISPLAY;
    EGLContext context=EGL_NO_CONTEXT;
    EGLSurface surface=EGL_NO_SURFACE;
    ANativeWindow* window=nullptr;
    PFNEGLPRESENTATIONTIMEANDROIDPROC presentation=nullptr;
    int version=0;
    bool initialized=false;
    ~Output() {
        if (display!=EGL_NO_DISPLAY && initialized) {
            if (context!=EGL_NO_CONTEXT && eglGetCurrentContext()==context)
                eglMakeCurrent(display,EGL_NO_SURFACE,EGL_NO_SURFACE,EGL_NO_CONTEXT);
            if (surface!=EGL_NO_SURFACE) eglDestroySurface(display,surface);
            if (context!=EGL_NO_CONTEXT) eglDestroyContext(display,context);
            eglTerminate(display);
        }
        if (window) ANativeWindow_release(window);
    }
    void open(JNIEnv* env,jobject java_surface) {
        window=ANativeWindow_fromSurface(env,java_surface);
        require(window!=nullptr,"ANativeWindow unavailable");
        display=eglGetDisplay(EGL_DEFAULT_DISPLAY);
        require(display!=EGL_NO_DISPLAY,"EGL display unavailable");
        require(eglInitialize(display,nullptr,nullptr),"EGL initialization failed");
        initialized=true;
        require(eglBindAPI(EGL_OPENGL_ES_API),"OpenGL ES API unavailable");
        EGLConfig config=nullptr;
        for (int attempt=3;attempt>=2;--attempt) {
            const EGLint attrs[]={EGL_SURFACE_TYPE,EGL_WINDOW_BIT,
                EGL_RENDERABLE_TYPE,attempt==3 ? EGL_OPENGL_ES3_BIT_KHR : EGL_OPENGL_ES2_BIT,
                EGL_RED_SIZE,8,EGL_GREEN_SIZE,8,EGL_BLUE_SIZE,8,EGL_ALPHA_SIZE,8,EGL_NONE};
            EGLint count=0;
            if (!eglChooseConfig(display,attrs,&config,1,&count) || count!=1) continue;
            const EGLint context_attrs[]={EGL_CONTEXT_CLIENT_VERSION,attempt,EGL_NONE};
            context=eglCreateContext(display,config,EGL_NO_CONTEXT,context_attrs);
            if (context!=EGL_NO_CONTEXT) { version=attempt; break; }
        }
        require(context!=EGL_NO_CONTEXT,"Neither GLES3 nor GLES2 context available");
        EGLint visual=0;
        require(eglGetConfigAttrib(display,config,EGL_NATIVE_VISUAL_ID,&visual),"No native visual");
        require(ANativeWindow_setBuffersGeometry(window,0,0,visual)==0,"Cannot set window format");
        surface=eglCreateWindowSurface(display,config,window,nullptr);
        require(surface!=EGL_NO_SURFACE,"Cannot create window EGL surface");
        current();
        require(eglSwapInterval(display,1),"Cannot enable swap interval");
        if (extension(eglQueryString(display,EGL_EXTENSIONS),"EGL_ANDROID_presentation_time"))
            presentation=reinterpret_cast<PFNEGLPRESENTATIONTIMEANDROIDPROC>(eglGetProcAddress("eglPresentationTimeANDROID"));
    }
    void current() { require(eglMakeCurrent(display,surface,surface,context),"Context/surface lost"); }
};
Output* output(jlong h) { return reinterpret_cast<Output*>(h); }
void error(JNIEnv* env,const std::exception& e) {
    env->ThrowNew(env->FindClass("java/lang/IllegalStateException"),e.what());
}
}
extern "C" JNIEXPORT jlong JNICALL Java_org_metaport_port_EglOutput_nativeCreate(JNIEnv* env,jclass,jobject surface) {
    try {
        auto value=std::make_unique<Output>();
        value->open(env,surface);
        return reinterpret_cast<jlong>(value.release());
    } catch (const std::exception& e) { error(env,e); return 0; }
}
extern "C" JNIEXPORT void JNICALL Java_org_metaport_port_EglOutput_nativeMakeCurrent(JNIEnv* env,jclass,jlong h) {
    try { output(h)->current(); } catch (const std::exception& e) { error(env,e); }
}
extern "C" JNIEXPORT jintArray JNICALL Java_org_metaport_port_EglOutput_nativeSize(JNIEnv* env,jclass,jlong h) {
    try {
        auto* o=output(h); EGLint width=0,height=0;
        require(eglQuerySurface(o->display,o->surface,EGL_WIDTH,&width),"Cannot query width");
        require(eglQuerySurface(o->display,o->surface,EGL_HEIGHT,&height),"Cannot query height");
        jintArray result=env->NewIntArray(2);
        if (result) { const jint size[]={width,height}; env->SetIntArrayRegion(result,0,2,size); }
        return result;
    } catch (const std::exception& e) { error(env,e); return nullptr; }
}
extern "C" JNIEXPORT jint JNICALL Java_org_metaport_port_EglOutput_nativeVersion(JNIEnv*,jclass,jlong h) { return output(h)->version; }
extern "C" JNIEXPORT jboolean JNICALL Java_org_metaport_port_EglOutput_nativePresentationSupported(JNIEnv*,jclass,jlong h) { return output(h)->presentation!=nullptr; }
extern "C" JNIEXPORT void JNICALL Java_org_metaport_port_EglOutput_nativePresent(JNIEnv* env,jclass,jlong h,jlong timestamp) {
    try {
        auto* o=output(h);
        o->current();
        if (timestamp!=0) {
            require(o->presentation!=nullptr,"Presentation timestamp unsupported");
            require(o->presentation(o->display,o->surface,timestamp),"Presentation timestamp failed");
        }
        require(eglSwapBuffers(o->display,o->surface),"Swap failed; surface/context may be lost");
    } catch (const std::exception& e) { error(env,e); }
}
extern "C" JNIEXPORT void JNICALL Java_org_metaport_port_EglOutput_nativeDestroy(JNIEnv*,jclass,jlong h) { delete output(h); }
