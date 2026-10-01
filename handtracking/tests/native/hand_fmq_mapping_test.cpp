// SPDX-License-Identifier: GPL-3.0-only
#include "hand_fmq_mapping.hpp"
#include <cassert>
#include <limits>
#include <initializer_list>
using namespace metaport::hand;
static void rejected(uint32_t offset, uint64_t extent, uint64_t size, size_t page) {
    GrantorMappingPlan p{11,22,33};
    assert(!plan_hand_fmq_mapping(offset,extent,size,page,p));
    assert(p.file_offset==11 && p.mapping_length==22 && p.data_delta==33);
}
int main() {
    GrantorMappingPlan p{};
    // Original 16 * 528-byte queue: grantors 0/8, 8/8, 16/8448, 8464/4.
    const uint32_t offsets[]={0,8,16,8464};
    const uint64_t extents[]={8,8,8448,4};
    for (size_t page : {size_t(4096),size_t(16384),size_t(65536)}) {
        for (size_t i=0;i<4;++i) {
            assert(plan_hand_fmq_mapping(offsets[i],extents[i],12288,page,p));
            assert(p.file_offset%page==0);
            assert(p.file_offset+p.data_delta==offsets[i]);
            assert(p.mapping_length==p.data_delta+extents[i]);
            assert(p.file_offset+p.mapping_length<=12288);
        }
    }
    assert(plan_hand_fmq_mapping(8464,4,12288,4096,p));
    assert(p.file_offset==8192 && p.data_delta==272 && p.mapping_length==276);
    assert(plan_hand_fmq_mapping(8464,4,12288,16384,p));
    assert(p.file_offset==0 && p.data_delta==8464 && p.mapping_length==8468);
    // Byte-identical calculations to the original masks for valid 4-KiB ranges.
    for (uint32_t offset=0;offset<131072;offset+=8) {
        assert(plan_hand_fmq_mapping(offset,528,131600,4096,p));
        assert(p.file_offset==(offset & 0xfffff000U));
        assert(p.data_delta==(offset & 0xfffU));
        assert(p.mapping_length==528+(offset & 0xfffU));
    }
    for (size_t page : {size_t(0),size_t(1),size_t(4095),size_t(6144),size_t(131072)})
        rejected(16,528,12288,page);
    rejected(17,528,12288,4096);
    rejected(16,0,12288,4096);
    rejected(0,0x7ffff000ULL,0xffffffffULL,4096);
    rejected(0x80000000U,8,0xffffffffULL,4096);
    rejected(16,8,15,16384);
    rejected(16,9,24,16384);
    rejected(0,std::numeric_limits<uint64_t>::max(),std::numeric_limits<uint64_t>::max(),4096);
    assert(plan_hand_fmq_mapping(16,8,24,16384,p)); // Exact end of FD range.
}
