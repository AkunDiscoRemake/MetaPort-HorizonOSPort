// SPDX-License-Identifier: GPL-3.0-only
#include <jni.h>
#include <stdint.h>
JNIEXPORT jint JNICALL Java_org_metaport_internal_cpuprobe_Probe_execute(JNIEnv *env,jclass cls,jint mode) {
    (void)env; (void)cls;
    uint32_t value=5,old=0,add=2;
    if(mode==1) {
        __asm__ volatile(".arch_extension lse\nldaddal %w0, %w1, [%2]"
                         : "+r"(add), "=&r"(old) : "r"(&value) : "memory");
        return old==5 ? (jint)value : -1;
    }
    if(mode==2) {
        uint8_t byte=7;
        __asm__ volatile(".arch_extension rcpc\nldaprb %w0, [%1]"
                         : "=r"(old) : "r"(&byte) : "memory");
        return (jint)old;
    }
    if(mode==3) {
        uint8_t byte=7;
        __asm__ volatile("ldarb %w0, [%1]" : "=r"(old) : "r"(&byte) : "memory");
        return (jint)old;
    }
    if(mode==4 || mode==5) {
        uint64_t wide=UINT64_C(0x1234567800000007),loaded;
        if(mode==4) {
            __asm__ volatile(".arch_extension rcpc\nldapr %0, [%1]"
                             : "=r"(loaded) : "r"(&wide) : "memory");
        } else {
            __asm__ volatile("ldar %0, [%1]" : "=r"(loaded) : "r"(&wide) : "memory");
        }
        return loaded==UINT64_C(0x1234567800000007) ? 7 : -1;
    }
    return (jint)(value+add);
}
