// SPDX-License-Identifier: GPL-3.0-only
#include "hand_u8_reduce.hpp"
#include <cassert>
#include <cstddef>
#include <limits>
using namespace metaport::hand;
using std::size_t;
static void check(const U8Vector128& a,const U8Vector128& b,U32Vector32 out,bool accumulate) {
    auto expected=out;
    for (size_t lane=0;lane<32;++lane) {
        uint64_t sum=accumulate?out[lane]:0;
        for (size_t j=0;j<4;++j) sum+=uint64_t(a[lane*4+j])*b[lane*4+j];
        expected[lane]=static_cast<uint32_t>(sum & 0xffffffffULL);
    }
    reduce_u8x4(a,b,out,accumulate);
    assert(out==expected);
}
static void check_signed(const U8Vector128& a,const S8Vector128& b,U32Vector32 out,bool accumulate) {
    auto expected=out;
    for (size_t lane=0;lane<32;++lane) {
        int64_t sum=accumulate?static_cast<int64_t>(out[lane]):0;
        for (size_t j=0;j<4;++j) sum+=int64_t(a[lane*4+j])*b[lane*4+j];
        expected[lane]=static_cast<uint32_t>(sum);
    }
    reduce_u8s8x4(a,b,out,accumulate);
    assert(out==expected);
}
static void check_coefficients(const U8Vector128& a,U32Vector32 initial,bool accumulate) {
    const std::array<uint8_t,4> u={0,127,128,255};
    const std::array<int8_t,4> s={-128,-1,0,127};
    auto unsigned_out=initial, signed_out=initial;
    reduce_u8x4_coefficients(a,u,unsigned_out,accumulate);
    reduce_u8s8x4_coefficients(a,s,signed_out,accumulate);
    for(size_t lane=0;lane<32;++lane) {
        uint64_t unsigned_sum=accumulate?initial[lane]:0;
        int64_t signed_sum=accumulate?static_cast<int64_t>(initial[lane]):0;
        for(size_t j=0;j<4;++j) {
            unsigned_sum+=uint64_t(a[lane*4+j])*u[j];
            signed_sum+=int64_t(a[lane*4+j])*s[j];
        }
        assert(unsigned_out[lane]==static_cast<uint32_t>(unsigned_sum));
        assert(signed_out[lane]==static_cast<uint32_t>(signed_sum));
    }
}
int main() {
    U8Vector128 a{},b{};S8Vector128 signed_b{};U32Vector32 out{};
    for (unsigned x=0;x<256;++x) for(unsigned y=0;y<256;++y) {
        a.fill(static_cast<uint8_t>(x));b.fill(static_cast<uint8_t>(y));
        signed_b.fill(static_cast<int8_t>(static_cast<int>(y)-128));
        check_signed(a,signed_b,out,false);
        check(a,b,out,false); // Includes values above signed-int8 range.
    }
    for(size_t i=0;i<128;++i) {a[i]=static_cast<uint8_t>(i);b[i]=static_cast<uint8_t>(255-i);}
    for(size_t i=0;i<32;++i) out[i]=std::numeric_limits<uint32_t>::max()-static_cast<uint32_t>(i);
    check(a,b,out,false);check(a,b,out,true);check(a,a,out,true);
    uint32_t seed=0x12345678u;
    for(int t=0;t<4096;++t) {
        for(size_t i=0;i<128;++i) {
            seed=seed*1664525u+1013904223u;a[i]=static_cast<uint8_t>(seed>>24);
            seed=seed*1664525u+1013904223u;b[i]=static_cast<uint8_t>(seed>>24);
            signed_b[i]=static_cast<int8_t>(static_cast<int>(b[i])-128);
        }
        check(a,b,out,true);check(a,b,out,false);
        check_signed(a,signed_b,out,true);check_signed(a,signed_b,out,false);
        check_coefficients(a,out,true);check_coefficients(a,out,false);
    }
    a.fill(255);b.fill(255);out.fill(0xffffffffu);
    reduce_u8x4(a,b,out,true);
    for(auto value:out) assert(value==260099u); // Wrap, not saturation.
    signed_b.fill(-128);out.fill(0);
    reduce_u8s8x4(a,signed_b,out,true);
    for(auto value:out) assert(value==0xfffe0200u); // -130560 lane bits.
    out.fill(0x80000000u);
    check_signed(a,signed_b,out,true); // Signed-boundary crossing, no C++ UB.
}
