// SPDX-License-Identifier: GPL-3.0-only
#include "hand_saturating_pack.hpp"
#include <cassert>
#include <cstddef>
#include <limits>
using namespace metaport::hand;
using std::size_t;

template<class T> T reference(int64_t value) {
    if (value < std::numeric_limits<T>::min()) return std::numeric_limits<T>::min();
    if (value > std::numeric_limits<T>::max()) return std::numeric_limits<T>::max();
    return static_cast<T>(value);
}
static void words(const PackWords& vu, const PackWords& vv) {
    PackHalves s{}; PackedUnsignedHalves u{};
    pack_s32_s16(vu, vv, s); pack_s32_u16(vu, vv, u);
    for (size_t i = 0; i < 32; ++i) {
        assert(s[i] == reference<int16_t>(vv[i]));
        assert(s[i + 32] == reference<int16_t>(vu[i]));
        assert(u[i] == reference<uint16_t>(vv[i]));
        assert(u[i + 32] == reference<uint16_t>(vu[i]));
    }
}
static void halves(const PackHalves& vu, const PackHalves& vv) {
    PackedBytes out{}; pack_s16_u8(vu, vv, out);
    for (size_t i = 0; i < 64; ++i) {
        assert(out[i] == reference<uint8_t>(vv[i]));
        assert(out[i + 64] == reference<uint8_t>(vu[i]));
    }
}
int main() {
    PackWords wu{}, wv{}; PackHalves hu{}, hv{};
    // Every possible signed halfword, and opposite source values to detect swaps.
    for (int32_t n = 0; n < 65536; ++n) {
        hu.fill(static_cast<int16_t>(32767 - n));
        hv.fill(static_cast<int16_t>(n - 32768));
        halves(hu, hv);
    }
    const int32_t edges[] = {INT32_MIN, -65536, -32769, -32768, -32767, -1,
                             0, 1, 254, 255, 256, 32766, 32767, 32768, 65534, 65535, 65536, INT32_MAX};
    for (int32_t a : edges) for (int32_t b : edges) {
        wu.fill(a); wv.fill(b); words(wu, wv);
    }
    // Unique in-range lanes detect interleaving, reversed chunks and source order.
    for (size_t i = 0; i < 64; ++i) {hv[i] = static_cast<int16_t>(i); hu[i] = static_cast<int16_t>(i + 64);}
    halves(hu, hv);
    for (size_t i = 0; i < 32; ++i) {wv[i] = static_cast<int32_t>(i); wu[i] = static_cast<int32_t>(i + 32);}
    words(wu, wv); words(wu, wu); halves(hu, hu);
    uint32_t seed = 0x1253u;
    for (int t = 0; t < 4096; ++t) {
        for (size_t i = 0; i < 32; ++i) {
            seed = seed * 1664525u + 1013904223u;
            wu[i] = static_cast<int32_t>(int64_t(seed) - 2147483648LL);
            seed = seed * 1664525u + 1013904223u;
            wv[i] = static_cast<int32_t>(int64_t(seed) - 2147483648LL);
        }
        words(wu, wv);
    }
}
