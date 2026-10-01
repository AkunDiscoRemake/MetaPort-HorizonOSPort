// SPDX-License-Identifier: GPL-3.0-only
#pragma once
#include <cstddef>
#include <cstdint>

namespace metaport::hand {
using std::size_t;
struct GrantorMappingPlan {
    uint64_t file_offset;
    size_t mapping_length;
    size_t data_delta;
};
// Hardware adaptation of original FMQ mapper 005a5134, not a private ABI bridge.
// Caller supplies actual OS page size and validated FD length; no syscalls here.
// Preserves grantor offset/extent, but replaces original fixed 4-KiB alignment.
// False leaves out unchanged. FD selection/ownership, mmap, event flags, atomics,
// permissions, and the private 528-byte payload are NOT implemented by this API.
bool plan_hand_fmq_mapping(uint32_t offset, uint64_t extent, uint64_t fd_size,
                           size_t page_size, GrantorMappingPlan& out) noexcept;
}
