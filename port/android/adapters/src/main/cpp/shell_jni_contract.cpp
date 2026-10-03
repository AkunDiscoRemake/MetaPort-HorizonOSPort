// SPDX-License-Identifier: GPL-3.0-only
#include "shell_jni_contract.hpp"
#include <type_traits>

// Compile-check original startup declarations against NDK JNI types.
// This translation unit does not implement or export any original JNI function.
namespace metaport::shell::contract {
static_assert(sizeof(jlong) == 8);
static_assert(std::is_same_v<nativeInit,
    jlong (JNICALL *)(JNIEnv*, jclass, jobject, jlong, jstring, jstring, jboolean, jboolean)>);
static_assert(std::is_same_v<nativeOnDestroy, void (JNICALL *)(JNIEnv*, jclass)>);
static_assert(std::is_same_v<nativeOnSizeChanged, void (JNICALL *)(JNIEnv*, jclass, jint, jint, jint)>);
static_assert(std::is_same_v<nativeFrameCommand, void (JNICALL *)(JNIEnv*, jclass, jstring)>);
}
