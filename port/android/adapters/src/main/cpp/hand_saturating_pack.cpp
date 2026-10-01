// SPDX-License-Identifier: GPL-3.0-only
#include "hand_saturating_pack.hpp"
#include <cstddef>
#if defined(__aarch64__)
#include <arm_neon.h>
#endif

namespace metaport::hand {
using std::size_t;
void pack_s32_s16(const PackWords& vu, const PackWords& vv, PackHalves& out) noexcept {
    PackHalves result{};
#if defined(__aarch64__)
    for (size_t i = 0; i < 32; i += 4) {
        vst1_s16(result.data() + i, vqmovn_s32(vld1q_s32(vv.data() + i)));
        vst1_s16(result.data() + 32 + i, vqmovn_s32(vld1q_s32(vu.data() + i)));
    }
#else
    for (size_t i = 0; i < 64; ++i) {
        const int32_t value = i < 32 ? vv[i] : vu[i - 32];
        result[i] = static_cast<int16_t>(value < -32768 ? -32768 : value > 32767 ? 32767 : value);
    }
#endif
    out = result;
}
void pack_s32_u16(const PackWords& vu, const PackWords& vv, PackedUnsignedHalves& out) noexcept {
    PackedUnsignedHalves result{};
#if defined(__aarch64__)
    for (size_t i = 0; i < 32; i += 4) {
        vst1_u16(result.data() + i, vqmovun_s32(vld1q_s32(vv.data() + i)));
        vst1_u16(result.data() + 32 + i, vqmovun_s32(vld1q_s32(vu.data() + i)));
    }
#else
    for (size_t i = 0; i < 64; ++i) {
        const int32_t value = i < 32 ? vv[i] : vu[i - 32];
        result[i] = static_cast<uint16_t>(value < 0 ? 0 : value > 65535 ? 65535 : value);
    }
#endif
    out = result;
}
void pack_s16_u8(const PackHalves& vu, const PackHalves& vv, PackedBytes& out) noexcept {
    PackedBytes result{};
#if defined(__aarch64__)
    for (size_t i = 0; i < 64; i += 8) {
        vst1_u8(result.data() + i, vqmovun_s16(vld1q_s16(vv.data() + i)));
        vst1_u8(result.data() + 64 + i, vqmovun_s16(vld1q_s16(vu.data() + i)));
    }
#else
    for (size_t i = 0; i < 128; ++i) {
        const int32_t value = i < 64 ? vv[i] : vu[i - 64];
        result[i] = static_cast<uint8_t>(value < 0 ? 0 : value > 255 ? 255 : value);
    }
#endif
    out = result;
}
}
