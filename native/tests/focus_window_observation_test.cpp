// SPDX-License-Identifier: GPL-3.0-only
#include "focus_window_observation.hpp"
#include <cassert>
using namespace metaport::focus;
int main() {
    WindowObservation state;
    assert(!state.known() && !state.matches(0,0));
    auto first=state.attach();assert(first>0 && !state.known());
    bool rejected=false;try { state.attach(); } catch (const std::logic_error&) { rejected=true; }
    assert(rejected);
    auto initial=state.generation();state.observe(first,true);
    auto focused=state.generation();assert(focused>initial && state.matches(first,focused));
    state.observe(first,true);assert(!state.matches(first,focused));
    assert(state.matches(first,state.generation()));
    state.observe(first,false);assert(!state.known() && !state.matches(first,state.generation()));
    state.observe(first,true);focused=state.generation();
    state.detach(first);assert(!state.known() && !state.matches(first,focused));
    state.detach(first);
    auto second=state.attach();assert(second!=first && !state.known());
    state.observe(second,true);auto replacement=state.generation();
    state.detach(first);assert(state.matches(second,replacement));
    rejected=false;try { state.observe(first,true); } catch (const std::logic_error&) { rejected=true; }
    assert(rejected && state.matches(second,replacement));
    state.detach(second);assert(!state.known());
}
