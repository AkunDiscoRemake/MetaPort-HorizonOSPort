// SPDX-License-Identifier: GPL-3.0-only
#pragma once
#include <array>
#include <cstdint>
namespace metaport::hand {
using U8Vector128 = std::array<uint8_t, 128>;
using U32Vector32 = std::array<uint32_t, 32>;
// Isolated arithmetic seen as .uw =/+= vrmpy(.ub,.ub) in original V69 backend.
// Models 128 input bytes, NOT a tensor layout or evidence of runtime HVX length.
// Per lane: out[i] = (accumulate ? old[i] : 0) + sum(a[4*i+j]*b[4*i+j]).
// Arithmetic wraps modulo 2^32. No scaling, signed weights, saturation or QFloat.
// No heap allocation, no private ABI, no model execution; caller owns synchronization.
void reduce_u8x4(const U8Vector128& a, const U8Vector128& b,
                 U32Vector32& out, bool accumulate) noexcept;
}
