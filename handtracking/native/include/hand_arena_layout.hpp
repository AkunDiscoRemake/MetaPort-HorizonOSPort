// SPDX-License-Identifier: GPL-3.0-only
#pragma once
#include <cstddef>
namespace metaport::hand {
// Arithmetic isolated from libtrackingengines FUN_00e1ec40 (ELF 0xd1ec40).
// NOT an allocator, a private ABI or a substitute for Qualcomm RPC memory.
enum class ArenaAlignment : size_t { Bytes16 = 16, Bytes128 = 128 };
// Caller supplies the already-aligned accumulated size. No allocation/write to
// next on failure. Overflow rejection is MetaPort hardening, not an original claim.
bool append_planned_block(size_t used, size_t bytes, ArenaAlignment alignment,
                          size_t& next) noexcept;
}
