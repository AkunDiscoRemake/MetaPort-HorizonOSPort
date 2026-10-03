// SPDX-License-Identifier: GPL-3.0-only
#include "space_data.hpp"
#include <array>
#include <cassert>
#include <cstdint>
#include <cstring>
using namespace metaport::spaces;
int main() {
    const Layout layouts[]={Layout::LegacySpace55,Layout::BaseSpaceCb,Layout::VirtualSpaceCb,Layout::WindowSpaceCb};
    for (unsigned k=0;k<4;k++) for (unsigned seed=0;seed<256;seed++) {
        std::array<std::uint8_t,256> src{},dst{};
        for (unsigned i=0;i<src.size();i++) src[i]=static_cast<std::uint8_t>(seed+i*31);
        dst.fill(0xa5);
        auto* out=dst.data()+1; // Deliberately unaligned; do not cast to C structs.
        out[0]=k?0xcb:0x55;out[1]=out[2]=out[3]=0;
        if (k>=2) {out[4]=static_cast<std::uint8_t>(k-1);out[5]=out[6]=out[7]=0;}
        auto before=dst;
        const std::size_t size=k<2?0x74:(k==2?0x10:0x14);
        assert(copy_payload(layouts[k],src.data()+1,size,out,size+8)==CopyStatus::Copied);
        assert(std::memcmp(out+8,src.data()+1,size)==0);
        assert(std::memcmp(dst.data(),before.data(),9)==0);
        assert(std::memcmp(out+8+size,before.data()+9+size,dst.size()-9-size)==0);
        dst=before;
        assert(copy_payload(layouts[k],src.data(),size-1,out,size+8)==CopyStatus::InvalidBuffer);
        assert(dst==before);
        assert(copy_payload(layouts[k],src.data(),size,out,size+7)==CopyStatus::InvalidBuffer);
        assert(dst==before);
        out[0]=0;before=dst;
        assert(copy_payload(layouts[k],src.data(),size,out,size+8)==CopyStatus::UnsupportedHeader);
        assert(dst==before);
    }
    std::array<std::uint8_t,256> overlap{};
    overlap[0]=0x55;
    auto before=overlap;
    assert(copy_payload(Layout::LegacySpace55,overlap.data(),116,overlap.data(),124)==CopyStatus::Overlap);
    assert(copy_payload(Layout::LegacySpace55,overlap.data()+8,116,overlap.data(),124)==CopyStatus::Overlap);
    assert(copy_payload(Layout::LegacySpace55,overlap.data(),116,overlap.data()+8,124)==CopyStatus::Overlap);
    assert(overlap==before);
    assert(copy_payload(Layout::BaseSpaceCb,nullptr,116,overlap.data(),124)==CopyStatus::InvalidBuffer);
    assert(copy_payload(Layout::BaseSpaceCb,overlap.data(),116,nullptr,124)==CopyStatus::InvalidBuffer);
    assert(copy_payload(static_cast<Layout>(99),overlap.data(),116,overlap.data(),124)==CopyStatus::InvalidBuffer);
    std::array<std::uint8_t,20> src{};
    overlap[0]=0xcb;overlap[4]=2;before=overlap;
    assert(copy_payload(Layout::VirtualSpaceCb,src.data(),16,overlap.data(),24)==CopyStatus::UnsupportedHeader);
    assert(overlap==before);
}
