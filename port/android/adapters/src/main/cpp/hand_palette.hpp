// SPDX-License-Identifier: GPL-3.0-only
#pragma once
#include <array>
#include <cstddef>
#include <cstdint>

namespace metaport::hand {
// Internal MetaPort transport utility, NOT a Horizon ABI or pose producer.
// Configure at asset-load time, then share immutably. Caller owns synchronization
// and supplies already-valid original bone records with an explicit record size.
// No assumptions about matrices, quaternion order, coordinate systems or units.
class PalettePlan final {
public:
    enum class Result { Ok, NotConfigured, InvalidPalette, InvalidBuffer, Overlap };
    Result configure(const uint32_t* palette, size_t count, size_t source_bones,
                     size_t record_bytes) noexcept;
    Result gather(const void* source, size_t source_bytes,
                  void* destination, size_t destination_bytes) const noexcept;
    size_t source_bytes() const noexcept { return source_bytes_; }
    size_t output_bytes() const noexcept { return output_bytes_; }
    size_t copy_runs() const noexcept { return runs_; }
private:
    struct Run { size_t source, destination, bytes; };
    std::array<Run, 512> copies_{};
    size_t runs_ = 0, source_bytes_ = 0, output_bytes_ = 0;
};
}
