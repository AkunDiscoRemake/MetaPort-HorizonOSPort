// SPDX-License-Identifier: GPL-3.0-only
#include "focus_session_state.hpp"
#include <cassert>
#include <thread>
using namespace metaport::focus;

int main() {
    SessionState state;
    assert(state.snapshot().empty());
    assert(!state.contains({10001,20}));
    const auto rejected = state.apply(10, 11, std::nullopt, 0);
    assert(rejected.access == Access::CallingPidMismatch && !rejected.notify_top_activity);
    assert(state.snapshot().empty());
    for (int code : {0, 1, 2, -1, 5}) {
        bool threw = false;
        try { state.apply(10, 10, std::nullopt, code); }
        catch (const std::bad_optional_access&) { threw = true; }
        assert(threw && state.snapshot().empty());
    }
    const auto visible = state.apply(20, 20, 10001, 0);
    assert(visible.membership_changed && visible.notify_top_activity);
    assert(visible.report_immersive_app_update && !visible.refresh_activity_state);
    assert(state.contains({10001,20}));
    assert(!state.contains({10002,20}));
    const auto again = state.apply(20, 20, 10001, 0);
    assert(!again.membership_changed && again.notify_top_activity && again.report_immersive_app_update);
    for (int code : {-1, 1, 3, 4, 5, 6, 7, 8, 2147483647}) {
        const auto ignored = state.apply(20, 20, 10001, code);
        assert(!ignored.membership_changed && !ignored.notify_top_activity);
        assert(!ignored.refresh_activity_state && !ignored.report_immersive_app_update);
        assert(state.snapshot().size() == 1);
    }
    state.apply(19, 19, 10002, 0);
    state.apply(21, 21, 10001, 0);
    const auto snapshot = state.snapshot();
    assert((snapshot == std::vector<Client>{{10001,20},{10001,21},{10002,19}}));
    const auto stop = state.apply(20, 20, 10001, 2);
    assert(stop.membership_changed && stop.refresh_activity_state && stop.notify_top_activity);
    assert(!state.contains({10001,20}));
    const auto stop_again = state.apply(20, 20, 10001, 2);
    assert(!stop_again.membership_changed && stop_again.refresh_activity_state);
    assert(stop_again.notify_top_activity && stop_again.report_immersive_app_update);
    // UID is part of identity: stopping a different observed UID cannot erase another client.
    state.apply(21, 21, 10002, 2);
    assert(state.snapshot().size() == 2);
    SessionState concurrent;
    std::vector<std::thread> threads;
    for (int i=0; i<8; ++i) threads.emplace_back([&,i] {
        for (int n=0; n<1000; ++n) {
            concurrent.apply(100+i,100+i,10001,0);
            concurrent.snapshot();
            assert(concurrent.contains({10001,100+i}));
            concurrent.apply(100+i,100+i,10001,2);
        }
    });
    for (auto& thread : threads) thread.join();
    assert(concurrent.snapshot().empty());
}
