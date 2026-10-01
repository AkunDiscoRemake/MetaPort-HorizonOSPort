// SPDX-License-Identifier: GPL-3.0-only
#include "hand_fmq_mapping.hpp"
#include <limits>

namespace metaport::hand {
bool plan_hand_fmq_mapping(uint32_t offset, uint64_t extent, uint64_t fd_size,
                           size_t page_size, GrantorMappingPlan& out) noexcept {
    // Limits/8-byte alignment from the recovered original mapping/descriptor path.
    // Page-size, zero-length, FD-range and overflow guards are adapter safeguards.
    if (page_size < 4096 || page_size > 65536 || (page_size & (page_size - 1)) != 0 ||
        (offset & 7) != 0 || offset > 0x7fffffffU || extent == 0 || extent >= 0x7ffff000ULL ||
        offset > fd_size || extent > fd_size - offset) return false;
    const uint64_t base = uint64_t(offset) & ~(uint64_t(page_size) - 1);
    const uint64_t delta = uint64_t(offset) - base;
    if (extent > std::numeric_limits<size_t>::max() - delta) return false;
    const GrantorMappingPlan candidate{base, static_cast<size_t>(extent + delta),
                                       static_cast<size_t>(delta)};
    out = candidate;
    return true;
}
}
