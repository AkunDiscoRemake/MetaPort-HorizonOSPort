// SPDX-License-Identifier: GPL-3.0-only
#pragma once
#include <cstddef>
namespace metaport::spaces {
// Bounded adaptation of original byte-copy conversions; NOT the private C ABI.
// Unknown field meanings/units/clocks remain uninterpreted. No pose generation.
enum class Layout { LegacySpace55, BaseSpaceCb, VirtualSpaceCb, WindowSpaceCb };
enum class CopyStatus { Copied, InvalidBuffer, UnsupportedHeader, Overlap };
// Caller supplies valid memory extents and an initialized little-endian header.
// Header/padding and bytes outside the observed payload are preserved. Inputs
// and entire destination extent must not overlap. No ownership is transferred.
CopyStatus copy_payload(Layout layout, const void* source, std::size_t source_bytes,
                        void* destination, std::size_t destination_bytes) noexcept;
}
