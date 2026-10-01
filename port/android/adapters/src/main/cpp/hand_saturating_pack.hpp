// SPDX-License-Identifier: GPL-3.0-only
#pragma once
#include <array>
#include <cstdint>

namespace metaport::hand {
using PackWords = std::array<int32_t, 32>;
using PackHalves = std::array<int16_t, 64>;
using PackedUnsignedHalves = std::array<uint16_t, 64>;
using PackedBytes = std::array<uint8_t, 128>;

// Output arithmetic of observed HVX vpack forms, for 128-byte input vectors.
// Crucial ordering: SECOND source Vv fills the lower half, FIRST Vu the upper.
// Not an ISA emulator: no DSP status/predicate/packet state, tensor layout,
// quantization scales or private ABI. NEON saturation may set ARM FPSR.QC.
// No heap allocations. Valid typed arrays required; caller owns synchronization.
void pack_s32_s16(const PackWords& vu, const PackWords& vv, PackHalves& out) noexcept;
void pack_s32_u16(const PackWords& vu, const PackWords& vv, PackedUnsignedHalves& out) noexcept;
void pack_s16_u8(const PackHalves& vu, const PackHalves& vv, PackedBytes& out) noexcept;
}
