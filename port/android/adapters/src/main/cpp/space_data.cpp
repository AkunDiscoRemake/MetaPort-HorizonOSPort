// SPDX-License-Identifier: GPL-3.0-only
#include "space_data.hpp"
#include <cstdint>
#include <cstring>
namespace metaport::spaces {
namespace {
std::uint32_t read32(const std::uint8_t* p) noexcept {
    return std::uint32_t(p[0]) | (std::uint32_t(p[1]) << 8) |
           (std::uint32_t(p[2]) << 16) | (std::uint32_t(p[3]) << 24);
}
}
CopyStatus copy_payload(Layout layout, const void* source, std::size_t source_bytes,
                        void* destination, std::size_t destination_bytes) noexcept {
    std::size_t payload = 0;
    std::uint32_t version = 0, type = 0;
    switch (layout) {
    case Layout::LegacySpace55: payload=0x74; version=0x55; break;
    case Layout::BaseSpaceCb: payload=0x74; version=0xcb; break;
    case Layout::VirtualSpaceCb: payload=0x10; version=0xcb; type=1; break;
    case Layout::WindowSpaceCb: payload=0x14; version=0xcb; type=2; break;
    default: return CopyStatus::InvalidBuffer;
    }
    if (!source || !destination || source_bytes<payload || destination_bytes<payload+8)
        return CopyStatus::InvalidBuffer;
    const auto src=reinterpret_cast<std::uintptr_t>(source);
    const auto dst=reinterpret_cast<std::uintptr_t>(destination);
    // Subtractions avoid overflow in end-address arithmetic.
    if ((src<=dst && dst-src<source_bytes) || (src>dst && src-dst<destination_bytes))
        return CopyStatus::Overlap;
    auto* out=static_cast<std::uint8_t*>(destination);
    if (read32(out)!=version || (type && read32(out+4)!=type))
        return CopyStatus::UnsupportedHeader;
    // Original ARM64 routines only load/store these bytes; no arithmetic on
    // floats. memcpy preserves raw NaN/flag/ID bits and the untouched prefix.
    std::memcpy(out+8, source, payload);
    return CopyStatus::Copied;
}
}
