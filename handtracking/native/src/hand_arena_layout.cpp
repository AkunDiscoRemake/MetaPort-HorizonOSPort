// SPDX-License-Identifier: GPL-3.0-only
#include "hand_arena_layout.hpp"
#include <limits>
namespace metaport::hand {
bool append_planned_block(size_t used, size_t bytes, ArenaAlignment alignment,
                          size_t& next) noexcept {
    const size_t a = static_cast<size_t>(alignment);
    if (a != 16 && a != 128) return false;
    const size_t mask = a - 1;
    const size_t limit = std::numeric_limits<size_t>::max();
    if ((used & mask) != 0 || bytes > limit - used) return false;
    const size_t sum = used + bytes;
    if (sum > limit - mask) return false;
    next = (sum + mask) & ~mask;
    return true;
}
}
