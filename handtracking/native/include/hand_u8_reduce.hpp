// SPDX-License-Identifier: GPL-3.0-only
#pragma once
#include <array>
#include <cstdint>
namespace metaport::hand {
using U8Vector128 = std::array<uint8_t, 128>;
using S8Vector128 = std::array<int8_t, 128>;
using U32Vector32 = std::array<uint32_t, 32>;
// Isolated arithmetic seen as .uw =/+= vrmpy(.ub,.ub) in original V69 backend.
// Models 128 input bytes, NOT a tensor layout or evidence of runtime HVX length.
// Per lane: out[i] = (accumulate ? old[i] : 0) + sum(a[4*i+j]*b[4*i+j]).
// Arithmetic wraps modulo 2^32. No scaling, saturation or QFloat.
// No heap allocation, no private ABI, no model execution; caller owns synchronization.
void reduce_u8x4(const U8Vector128& a, const U8Vector128& b,
                 U32Vector32& out, bool accumulate) noexcept;
// Mixed unsigned input / signed weight variant. Output contains 32-bit lane bits,
// not a signed C++ accumulator (signed overflow must never be invoked).
void reduce_u8s8x4(const U8Vector128& a, const S8Vector128& b,
                   U32Vector32& out, bool accumulate) noexcept;
// Scalar-register forms: coefficient j is byte j of Rt, low byte first.
// Explicit byte arrays avoid host endianness or private register ABI assumptions.
void reduce_u8x4_coefficients(const U8Vector128& a, const std::array<uint8_t, 4>& b,
                              U32Vector32& out, bool accumulate) noexcept;
void reduce_u8s8x4_coefficients(const U8Vector128& a, const std::array<int8_t, 4>& b,
                                U32Vector32& out, bool accumulate) noexcept;
}
