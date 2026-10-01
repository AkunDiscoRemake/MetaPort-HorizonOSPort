cmake_minimum_required(VERSION 3.22.1)
project(MetaPortHandTracking VERSION 0.1.0 LANGUAGES CXX)

set(HANDTRACKING_SOURCES
    native/src/hand_palette.cpp
    native/src/hand_material.cpp
    native/src/hand_arena_layout.cpp
    native/src/hand_u8_reduce.cpp
    native/src/hand_saturating_pack.cpp
    native/src/hand_fmq_mapping.cpp)
add_library(metaport_handtracking_objects OBJECT ${HANDTRACKING_SOURCES})
target_include_directories(metaport_handtracking_objects PUBLIC "${CMAKE_CURRENT_SOURCE_DIR}/native/include")
target_compile_features(metaport_handtracking_objects PUBLIC cxx_std_17)
target_compile_options(metaport_handtracking_objects PRIVATE -Wall -Wextra -Werror)
set_target_properties(metaport_handtracking_objects PROPERTIES POSITION_INDEPENDENT_CODE ON)
# Standalone consumers can link this archive; MetaPort links the object target
# so that currently unreferenced helper translation units are not discarded.
add_library(metaport_handtracking STATIC $<TARGET_OBJECTS:metaport_handtracking_objects>)
target_include_directories(metaport_handtracking PUBLIC "${CMAKE_CURRENT_SOURCE_DIR}/native/include")
target_compile_features(metaport_handtracking PUBLIC cxx_std_17)

option(METAPORT_HANDTRACKING_BUILD_TESTS "Build isolated arithmetic tests (not inference)" OFF)
if(METAPORT_HANDTRACKING_BUILD_TESTS)
    enable_testing()
    foreach(name hand_palette hand_material hand_arena_layout hand_u8_reduce hand_saturating_pack hand_fmq_mapping)
        add_executable(${name}_test tests/native/${name}_test.cpp)
        target_link_libraries(${name}_test PRIVATE metaport_handtracking)
        target_compile_options(${name}_test PRIVATE -Wall -Wextra -Werror -UNDEBUG)
        add_test(NAME ${name} COMMAND ${name}_test)
    endforeach()
endif()
