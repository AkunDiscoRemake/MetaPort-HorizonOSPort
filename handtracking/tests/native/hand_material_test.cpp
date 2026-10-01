// SPDX-License-Identifier: GPL-3.0-only
#include "hand_material.hpp"
#include <cassert>
#include <cmath>
#include <limits>
using metaport::hand::update_material_value;
int main() {
    std::array<float,4> state{0.f,1.f,2.f,3.f};
    assert(!update_material_value(state,state));
    auto next=state; next[0]=-0.f;
    assert(!update_material_value(state,next));
    assert(!std::signbit(state[0])); // Original no-write branch preserves old bits.
    for (int i=0;i<4;++i) {
        next=state; next[i]=std::nextafter(state[i],10.f);
        assert(update_material_value(state,next)); // No epsilon approximation.
        assert(state==next);
    }
    next.fill(std::numeric_limits<float>::infinity());
    assert(update_material_value(state,next));
    assert(!update_material_value(state,next));
    for (int i=0;i<4;++i) {
        next.fill(1.f); next[i]=std::numeric_limits<float>::quiet_NaN();
        assert(update_material_value(state,next));
        assert(update_material_value(state,next)); // NaNs remain unordered.
        assert(std::isnan(state[i]));
    }
}
