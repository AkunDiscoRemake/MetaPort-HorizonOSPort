// SPDX-License-Identifier: GPL-3.0-only
#include "hand_arena_layout.hpp"
#include <cassert>
#include <initializer_list>
#include <limits>
using namespace metaport::hand;
int main() {
    for (auto a : {ArenaAlignment::Bytes16, ArenaAlignment::Bytes128}) {
        const size_t alignment=static_cast<size_t>(a);
        size_t used=0, next=0;
        for (size_t bytes=0;bytes<1001;++bytes) {
            assert(append_planned_block(used,bytes,a,next));
            assert(next >= used+bytes);
            assert(next % alignment == 0);
            assert(next-(used+bytes) < alignment);
            used=next;
        }
        next=123;
        assert(!append_planned_block(1,4,a,next) && next==123);
        assert(!append_planned_block(0,std::numeric_limits<size_t>::max(),a,next) && next==123);
        const size_t last=std::numeric_limits<size_t>::max()-(alignment-1);
        assert(append_planned_block(last,0,a,next) && next==last);
        assert(!append_planned_block(last,1,a,next) && next==last);
        assert(!append_planned_block(last,alignment,a,next) && next==last);
    }
    size_t next=123;
    assert(!append_planned_block(0,4,static_cast<ArenaAlignment>(24),next) && next==123);
}
