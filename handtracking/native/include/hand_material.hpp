// SPDX-License-Identifier: GPL-3.0-only
#pragma once
#include <array>

namespace metaport::hand {
// Isolated value-update rule observed in libshell FUN_00a428e4, called by
// GhostHandRenderingSystem. Not the original material object's private ABI.
// Caller must supply initialized state and handle synchronization/dirty flags.
// Returns true only if the value was written. Do not compile with fast-math:
// original FCMEQ semantics distinguish NaN from itself, but equate signed zeros.
bool update_material_value(std::array<float, 4>& current,
                           const std::array<float, 4>& incoming) noexcept;
}
