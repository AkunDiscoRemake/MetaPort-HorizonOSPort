// SPDX-License-Identifier: GPL-3.0-only
#include "hand_palette.hpp"
#include <cstring>

namespace metaport::hand {
PalettePlan::Result PalettePlan::configure(const uint32_t* palette, size_t count,
                                          size_t source_bones, size_t stride) noexcept {
    // Clear old configuration on failure: never reuse a stale model's plan.
    runs_ = source_bytes_ = output_bytes_ = 0;
    if (!palette || count == 0 || count > 512 || source_bones == 0 ||
        source_bones > 512 || count > source_bones || stride == 0 || stride > 1024)
        return Result::InvalidPalette;
    for (size_t i = 0; i < count; ++i) {
        if (palette[i] >= source_bones || (i && palette[i] <= palette[i-1]))
            return Result::InvalidPalette;
    }
    for (size_t i = 0; i < count; ++i) {
        if (i && palette[i] == palette[i-1]+1) {
            copies_[runs_-1].bytes += stride;
        } else {
            copies_[runs_++] = {static_cast<size_t>(palette[i])*stride, i*stride, stride};
        }
    }
    source_bytes_ = source_bones*stride;
    output_bytes_ = count*stride;
    return Result::Ok;
}

PalettePlan::Result PalettePlan::gather(const void* source, size_t source_size,
                                       void* destination, size_t destination_size) const noexcept {
    if (!runs_) return Result::NotConfigured;
    if (!source || !destination || source_size < source_bytes_ || destination_size < output_bytes_)
        return Result::InvalidBuffer;
    const auto src = reinterpret_cast<uintptr_t>(source);
    const auto dst = reinterpret_cast<uintptr_t>(destination);
    // Subtraction avoids address addition overflow. Reject overlap before writes.
    if ((src <= dst && dst-src < source_bytes_) ||
        (dst < src && src-dst < output_bytes_)) return Result::Overlap;
    const auto* in = static_cast<const unsigned char*>(source);
    auto* out = static_cast<unsigned char*>(destination);
    for (size_t i = 0; i < runs_; ++i) {
        const auto& run = copies_[i];
        std::memcpy(out+run.destination, in+run.source, run.bytes);
    }
    return Result::Ok;
}
}
