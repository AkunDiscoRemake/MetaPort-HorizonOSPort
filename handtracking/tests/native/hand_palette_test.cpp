// SPDX-License-Identifier: GPL-3.0-only
#include "hand_palette.hpp"
#include <algorithm>
#include <array>
#include <cassert>
#include <cstring>
#include <vector>
using metaport::hand::PalettePlan;
using Result = PalettePlan::Result;
int main() {
    PalettePlan plan;
    assert(plan.gather(nullptr,0,nullptr,0)==Result::NotConfigured);
    const uint32_t palette[] = {0,1,5,7,8};
    assert(plan.configure(palette,5,79,64)==Result::Ok);
    assert(plan.copy_runs()==3 && plan.output_bytes()==320 && plan.source_bytes()==5056);
    std::vector<unsigned char> source(plan.source_bytes()), destination(321,0xcc);
    for (size_t i=0;i<source.size();++i) source[i]=static_cast<unsigned char>(i*37+i/64);
    assert(plan.gather(source.data(),source.size(),destination.data(),destination.size())==Result::Ok);
    for (size_t i=0;i<5;++i) assert(std::memcmp(destination.data()+i*64,source.data()+palette[i]*64,64)==0);
    assert(destination.back()==0xcc);
    std::fill(destination.begin(),destination.end(),0xcc);
    assert(plan.gather(source.data(),source.size()-1,destination.data(),321)==Result::InvalidBuffer);
    assert(plan.gather(source.data(),source.size(),destination.data(),319)==Result::InvalidBuffer);
    assert(plan.gather(nullptr,source.size(),destination.data(),321)==Result::InvalidBuffer);
    assert(std::all_of(destination.begin(),destination.end(),[](auto x){return x==0xcc;}));
    assert(plan.gather(source.data(),source.size(),source.data()+1,320)==Result::Overlap);
    assert(plan.gather(source.data()+1,source.size()-1,source.data(),320)==Result::InvalidBuffer);
    const uint32_t reverse[]={5,1};
    assert(plan.configure(reverse,2,79,64)==Result::InvalidPalette);
    assert(plan.gather(source.data(),source.size(),destination.data(),321)==Result::NotConfigured);
    const uint32_t duplicate[]={1,1};
    assert(plan.configure(duplicate,2,79,64)==Result::InvalidPalette);
    assert(plan.configure(palette,5,79,0)==Result::InvalidPalette);
    assert(plan.configure(palette,5,79,1025)==Result::InvalidPalette);
    assert(plan.configure(palette,5,8,64)==Result::InvalidPalette);
    // Exhaustive subset comparison for a small hierarchy; odd and aligned strides.
    for (size_t stride: {size_t(1),size_t(7),size_t(48),size_t(64)}) {
        for (unsigned mask=1;mask<256;++mask) {
            std::vector<uint32_t> selected;
            for (uint32_t i=0;i<8;++i) if(mask&(1u<<i)) selected.push_back(i);
            assert(plan.configure(selected.data(),selected.size(),8,stride)==Result::Ok);
            std::vector<unsigned char> output(plan.output_bytes()), reference;
            for(auto i:selected) reference.insert(reference.end(),source.begin()+i*stride,source.begin()+(i+1)*stride);
            assert(plan.gather(source.data(),source.size(),output.data(),output.size())==Result::Ok);
            assert(output==reference);
        }
    }
    assert(plan.configure(palette,5,79,1)==Result::Ok);
    assert(plan.gather(source.data()+1,79,source.data(),5)==Result::Overlap);
}
