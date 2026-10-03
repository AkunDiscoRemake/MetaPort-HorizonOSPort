// SPDX-License-Identifier: GPL-3.0-only
#include "hand_material.hpp"
#include <limits>
#include <cstring>
#if defined(__aarch64__)
#include <arm_neon.h>
#endif
#ifdef __FAST_MATH__
#error Original material comparison requires IEEE floating-point semantics
#endif
static_assert(std::numeric_limits<float>::is_iec559 && sizeof(float) == 4);
namespace metaport::hand {
bool update_material_value(std::array<float, 4>& current,
                           const std::array<float, 4>& incoming) noexcept {
#if defined(__aarch64__)
    auto equal = vceqq_f32(vld1q_f32(current.data()), vld1q_f32(incoming.data()));
    equal = vpminq_u32(equal, equal);
    equal = vpminq_u32(equal, equal);
    if (vgetq_lane_u32(equal, 0) == 0xffffffffu) return false;
#else
    if (current[0] == incoming[0] && current[1] == incoming[1] &&
        current[2] == incoming[2] && current[3] == incoming[3]) return false;
#endif
    // Preserve incoming object bits, including NaN payloads; self-alias is legal.
    std::memmove(current.data(), incoming.data(), 4 * sizeof(float));
    return true;
}
}
