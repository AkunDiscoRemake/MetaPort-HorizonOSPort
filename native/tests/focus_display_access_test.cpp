// SPDX-License-Identifier: GPL-3.0-only
#include "focus_display_access.hpp"
#include <cassert>
#include <thread>
#include <vector>

using namespace metaport::focus;

int main() {
    // 1. Permission gate (0x2dd60): UID 1041 bypasses PermissionCache; UID 0 does not.
    assert(!check_calling_permission(0, false));
    assert(check_calling_permission(0, true));
    assert(check_calling_permission(1041, false));
    assert(check_calling_permission(1041, true));
    assert(!check_calling_permission(1000, false));
    assert(check_calling_permission(1000, true));

    // 2. Initial state: FocusPolicy main_display_focus_ = true (0x22d50),
    // ConnectionManager active_displays_ = {0} (0x15480).
    DisplayTrackingAccessState state;
    assert(state.main_display_focus());
    assert((state.active_displays() == std::vector<std::int32_t>{0}));

    // Denied grant/revoke leaves main_display_focus_ and active_displays_ untouched.
    auto denied_revoke = state.revoke_tracking_service_access(10010, false, 0);
    assert(denied_revoke.status == DisplayAccessStatus::PermissionDenied);
    assert(state.main_display_focus());
    auto denied_grant = state.grant_tracking_service_access(0, false, 2);
    assert(denied_grant.status == DisplayAccessStatus::PermissionDenied);
    assert((state.active_displays() == std::vector<std::int32_t>{0}));

    // 3. Main display (display_id == 0): toggles main_display_focus_ (0x265d0)
    // without removing 0 from active_displays_ or emitting callback masks (0x21880 / 0x21b20).
    auto revoke_main = state.revoke_tracking_service_access(1000, true, 0);
    assert((revoke_main == DisplayAccessEffects{DisplayAccessStatus::Allowed, false, false, std::nullopt}));
    assert(!state.main_display_focus());
    assert((state.active_displays() == std::vector<std::int32_t>{0}));

    // UID 1041 bypass can re-grant display 0 even when permission_cache_granted == false.
    auto grant_main = state.grant_tracking_service_access(1041, false, 0);
    assert((grant_main == DisplayAccessEffects{DisplayAccessStatus::Allowed, true, false, std::nullopt}));
    assert(state.main_display_focus());

    // 4. Secondary displays and IDisplayManager callback mask transitions (0x21880 / 0x21b20):
    // size 1 -> 2 emits mask 2; duplicate or size 2 -> 3 emits nullopt;
    // size 3 -> 2 emits nullopt; size 2 -> 1 emits mask 0.
    auto grant_d2 = state.grant_tracking_service_access(1000, true, 2);
    assert((grant_d2 == DisplayAccessEffects{DisplayAccessStatus::Allowed, true, true, 2}));
    assert((state.active_displays() == std::vector<std::int32_t>{0, 2}));

    auto dup_d2 = state.grant_tracking_service_access(1000, true, 2);
    assert((dup_d2 == DisplayAccessEffects{DisplayAccessStatus::Allowed, true, false, std::nullopt}));

    auto grant_d5 = state.grant_tracking_service_access(1000, true, 5);
    assert((grant_d5 == DisplayAccessEffects{DisplayAccessStatus::Allowed, true, true, std::nullopt}));
    assert((state.active_displays() == std::vector<std::int32_t>{0, 2, 5}));

    // DisplayManagerCallback::onDisplayEvent (0x182e0): only event == 3 revokes secondary display;
    // display 0 on event == 3 does NOT clear main_display_focus_.
    auto ignored_event = state.on_display_event(2, 1);
    assert(!ignored_event.tracked_displays_changed);
    auto main_removed_event = state.on_display_event(0, 3);
    assert(!main_removed_event.tracked_displays_changed);
    assert(state.main_display_focus());

    auto d2_removed = state.on_display_event(2, 3);
    assert((d2_removed == DisplayAccessEffects{DisplayAccessStatus::Allowed, true, true, std::nullopt}));
    assert((state.active_displays() == std::vector<std::int32_t>{0, 5}));

    auto revoke_d5 = state.revoke_tracking_service_access(1000, true, 5);
    assert((revoke_d5 == DisplayAccessEffects{DisplayAccessStatus::Allowed, true, true, 0}));
    assert((state.active_displays() == std::vector<std::int32_t>{0}));

    auto revoke_missing = state.revoke_tracking_service_access(1000, true, 5);
    assert((revoke_missing == DisplayAccessEffects{DisplayAccessStatus::Allowed, true, false, std::nullopt}));

    // 5. ConnectionManager::onForegroundActivitiesChanged (0x20cc0) and
    // onForegroundServicesChanged (0x20860) display/activity classification.
    const Client c_main{10010, 501};
    const Client c_sec{10020, 502};
    const Client c_untracked{10030, 503};

    // Main display (0) top activity -> enters foreground_activities, top_activities, all_top_activities.
    auto e_main = state.on_foreground_activities_changed(c_main, true, {0});
    assert((e_main == ForegroundActivityEffects{true, true, true, true, true}));

    // Secondary tracked display (2) only -> enters top_activities and all_top_activities, NOT foreground_activities.
    auto e_sec = state.on_foreground_activities_changed(c_sec, true, {2});
    assert((e_sec == ForegroundActivityEffects{false, true, true, false, true}));

    // Foreground activity on an untracked display (matching_displays empty) -> enters all_top_activities only.
    auto e_untracked = state.on_foreground_activities_changed(c_untracked, true, {});
    assert((e_untracked == ForegroundActivityEffects{false, false, true, false, false}));

    assert((state.clients_with_foreground_activity() == std::vector<Client>{c_main}));
    assert((state.clients_with_top_activities() == std::vector<Client>{c_main, c_sec}));
    assert((state.all_clients_with_top_activities() == std::vector<Client>{c_main, c_sec, c_untracked}));

    // Moving c_sec from secondary display {2} to main display {0}:
    // foreground_activities changes (true), top_activities stays true (false).
    auto e_sec_to_main = state.on_foreground_activities_changed(c_sec, true, {0});
    assert((e_sec_to_main == ForegroundActivityEffects{true, false, false, true, false}));

    // Panel service (0x20860): service_types != 0 inserts, 0 erases.
    assert(state.on_foreground_services_changed(c_main, 1));
    assert(!state.on_foreground_services_changed(c_main, 4));
    assert((state.clients_with_foreground_panel_service() == std::vector<Client>{c_main}));
    assert(state.on_foreground_services_changed(c_main, 0));
    assert(state.clients_with_foreground_panel_service().empty());

    // 6. Concurrent stress test for TSan.
    std::thread modifier([&] {
        for (int i = 0; i < 300; ++i) {
            state.grant_tracking_service_access(1041, false, (i % 3));
            state.on_display_event((i % 3), (i & 1) ? 3 : 1);
            state.revoke_tracking_service_access(1000, true, (i % 3));
            state.on_foreground_activities_changed(
                Client{10000 + (i % 3), 600 + (i % 3)}, (i & 1) == 0, (i & 2) ? std::vector<int>{0} : std::vector<int>{2});
            state.on_foreground_services_changed(Client{10000, 600}, i & 1);
        }
    });
    std::thread observer([&] {
        for (int i = 0; i < 300; ++i) {
            (void)state.main_display_focus();
            (void)state.active_displays();
            (void)state.clients_with_foreground_activity();
            (void)state.clients_with_top_activities();
            (void)state.all_clients_with_top_activities();
            (void)state.clients_with_foreground_panel_service();
        }
    });
    modifier.join();
    observer.join();
    return 0;
}
