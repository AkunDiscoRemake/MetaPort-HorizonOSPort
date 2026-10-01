cmake_minimum_required(VERSION 3.22.1)
project(metaport_adapters LANGUAGES CXX)
add_library(metaport_adapters SHARED android_sensors.cpp egl_output.cpp input_router_jni.cpp hand_palette.cpp hand_material.cpp hand_arena_layout.cpp hand_u8_reduce.cpp hand_saturating_pack.cpp)
target_compile_features(metaport_adapters PRIVATE cxx_std_17)
target_compile_options(metaport_adapters PRIVATE -Wall -Wextra -Werror)
# Compatible ELF segment alignment for Android devices with 16 KiB pages.
target_link_options(metaport_adapters PRIVATE "-Wl,-z,max-page-size=16384")
target_link_libraries(metaport_adapters PRIVATE android log EGL GLESv2)
