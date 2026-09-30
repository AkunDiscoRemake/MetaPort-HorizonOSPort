// SPDX-License-Identifier: GPL-3.0-only
#include "hand_u8_reduce.hpp"
#include <cstddef>
using std::size_t;
#if defined(__aarch64__)
#include <arm_neon.h>
#endif
namespace metaport::hand {
void reduce_u8x4(const U8Vector128& a, const U8Vector128& b,
                 U32Vector32& out, bool accumulate) noexcept {
    U32Vector32 result{};
#if defined(__aarch64__)
    // Baseline ARM64 NEON, no optional dotprod feature or CPU detector required.
    // Widen before summation: pair sums can exceed 16 bits (2*255*255).
    for (size_t i=0; i<128; i+=16) {
        const auto va=vld1q_u8(a.data()+i), vb=vld1q_u8(b.data()+i);
        const auto lo=vpaddlq_u16(vmull_u8(vget_low_u8(va),vget_low_u8(vb)));
        const auto hi=vpaddlq_u16(vmull_u8(vget_high_u8(va),vget_high_u8(vb)));
        auto sums=vpaddq_u32(lo,hi);
        if (accumulate) sums=vaddq_u32(sums,vld1q_u32(out.data()+i/4));
        vst1q_u32(result.data()+i/4,sums);
    }
#else
    for (size_t i=0; i<32; ++i) {
        uint32_t sum=accumulate ? out[i] : 0;
        for (size_t j=0; j<4; ++j)
            sum+=static_cast<uint32_t>(a[4*i+j])*static_cast<uint32_t>(b[4*i+j]);
        result[i]=sum;
    }
#endif
    out=result;
}
}
