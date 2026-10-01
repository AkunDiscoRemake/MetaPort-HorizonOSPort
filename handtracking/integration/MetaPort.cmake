# SPDX-License-Identifier: GPL-3.0-only
# Both MetaPort and standalone CMake consumers use the same native sources.
function(metaport_use_handtracking target)
    if(NOT TARGET metaport_handtracking_objects)
        add_subdirectory("${CMAKE_CURRENT_FUNCTION_LIST_DIR}/.."
                         "${CMAKE_CURRENT_BINARY_DIR}/metaport-handtracking")
    endif()
    target_link_libraries(${target} PRIVATE metaport_handtracking_objects)
endfunction()
