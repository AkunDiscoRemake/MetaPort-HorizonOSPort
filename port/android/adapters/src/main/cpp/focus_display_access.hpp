// SPDX-License-Identifier: GPL-3.0-only
#pragma once
#include "focus_decision.hpp"
#include "focus_session_state.hpp"
#include <algorithm>
#include <cstdint>
#include <mutex>
#include <optional>
#include <set>
#include <string_view>
#include <vector>

namespace metaport::focus {

// Recovered from _GLOBAL__sub_I_VrFocusService.cpp (0xf5e0).
inline constexpr std::string_view kReadFocusStatePermission =
    "horizonos.permission.READ_FOCUS_STATE";
inline constexpr std::string_view kDumpPermission =
    "android.permission.DUMP";
inline constexpr std::string_view kGrantTrackingAccessPermission =
    "horizonos.permission.GRANT_TRACKING_SERVICE_ACCESS_TO_DISPLAY";

// DAT_0013d298 in _GLOBAL__sub_I_VrFocusService.cpp (0xf5e0): {0x411} (1041 = AID_AUDIOSERVER).
inline constexpr std::int32_t kCallingPermissionBypassUid = 1041;

// ConnectionManager::DisplayManagerCallback::onDisplayEvent (0x182e0): 182f8 cmp w2, #0x3.
inline constexpr std::int32_t kDisplayRemovedEvent = 3;

// ConnectionManager::grant/revokeTrackingServiceAccess (0x21880 / 0x21b20):
// IDisplayManager::registerCallbackWithEventMask(displayCallback, 2 / 0).
inline constexpr std::int32_t kDisplayCallbackMaskAddedRemovedChanged = 2;
inline constexpr std::int32_t kDisplayCallbackMaskNone = 0;

// Recovered from OVR::OS::VrFocusService::checkCallingPermission (0x2dd60):
// 2dd78: cbz w0, 2de38 (callingUid == 0 falls through to PermissionCache)
// 2dde4..2ddec: cmp w14, w0; b.eq 2de50 (callingUid == 1041 returns true directly).
inline bool check_calling_permission(std::int32_t calling_uid, bool permission_cache_granted) {
    if (calling_uid != 0 && calling_uid == kCallingPermissionBypassUid) {
        return true;
    }
    return permission_cache_granted;
}

enum class DisplayAccessStatus { Allowed, PermissionDenied };

struct DisplayAccessEffects {
    DisplayAccessStatus status = DisplayAccessStatus::PermissionDenied;
    bool main_display_focus = true;
    bool tracked_displays_changed = false;
    std::optional<std::int32_t> register_display_callback_mask{};

    bool operator==(const DisplayAccessEffects& other) const {
        return status == other.status &&
               main_display_focus == other.main_display_focus &&
               tracked_displays_changed == other.tracked_displays_changed &&
               register_display_callback_mask == other.register_display_callback_mask;
    }
};

struct ForegroundActivityEffects {
    bool foreground_activities_changed = false;
    bool top_activity_clients_changed = false;
    bool all_top_activity_clients_changed = false;
    bool report_immersive_app_update = false;
    bool notify_top_activity = false;

    bool operator==(const ForegroundActivityEffects& other) const {
        return foreground_activities_changed == other.foreground_activities_changed &&
               top_activity_clients_changed == other.top_activity_clients_changed &&
               all_top_activity_clients_changed == other.all_top_activity_clients_changed &&
               report_immersive_app_update == other.report_immersive_app_update &&
               notify_top_activity == other.notify_top_activity;
    }
};

// Recovered display tracking access and foreground activity/panel classification reducer:
// - FocusPolicy::FocusPolicy (0x22d50) & FocusPolicy::setMainDisplayFocus (0x265d0)
// - ConnectionManager::ConnectionManager (0x15480)
// - ConnectionManager::DisplayManagerCallback::onDisplayEvent (0x182e0)
// - ConnectionManager::onForegroundServicesChanged (0x20860)
// - ConnectionManager::onForegroundActivitiesChanged (0x20cc0)
// - ConnectionManager::getClientsWithForegroundActivity..getAllClientsWithTopActivities (0x21540..0x21740)
// - ConnectionManager::grant/revokeTrackingServiceAccess (0x21880 / 0x21b20)
// - VrFocusService::grant/revokeTrackingServiceAccess (0x2cb90 / 0x2ccc0)
class DisplayTrackingAccessState {
public:
    DisplayTrackingAccessState() : main_display_focus_(true), active_displays_{0} {}

    // VrFocusService::grantTrackingServiceAccess (0x2cb90):
    // - Checks GRANT_TRACKING_SERVICE_ACCESS_TO_DISPLAY via checkCallingPermission (0x2dd60).
    // - When display_id == 0: FocusPolicy::setMainDisplayFocus(true) (0x265d0);
    //   ConnectionManager::grantTrackingServiceAccess(0) returns immediately (218c8: cbz w21, 21a68).
    // - When display_id != 0: inserts display_id into active_displays_ (+0x1b8);
    //   if newly inserted and active_displays_.size() == 2 (21960: cmp x8, #0x2),
    //   requests IDisplayManager::registerCallbackWithEventMask(callback, 2) (21a14: mov w2, #0x2).
    DisplayAccessEffects grant_tracking_service_access(
        std::int32_t calling_uid,
        bool permission_cache_granted,
        std::int32_t display_id) {
        std::lock_guard<std::mutex> lock(mutex_);
        if (!check_calling_permission(calling_uid, permission_cache_granted)) {
            return {DisplayAccessStatus::PermissionDenied, main_display_focus_, false, std::nullopt};
        }
        if (display_id == 0) {
            main_display_focus_ = true;
            return {DisplayAccessStatus::Allowed, main_display_focus_, false, std::nullopt};
        }
        const auto [_, inserted] = active_displays_.insert(display_id);
        std::optional<std::int32_t> mask;
        if (inserted && active_displays_.size() == 2) {
            mask = kDisplayCallbackMaskAddedRemovedChanged;
        }
        return {DisplayAccessStatus::Allowed, main_display_focus_, inserted, mask};
    }

    // VrFocusService::revokeTrackingServiceAccess (0x2ccc0):
    // - Checks GRANT_TRACKING_SERVICE_ACCESS_TO_DISPLAY via checkCallingPermission (0x2dd60).
    // - When display_id == 0: FocusPolicy::setMainDisplayFocus(false) (0x265d0);
    //   ConnectionManager::revokeTrackingServiceAccess(0) returns immediately (21b44: cbz w1, 21d4c)
    //   so display 0 remains in active_displays_.
    // - When display_id != 0: erases display_id from active_displays_ (+0x1b8);
    //   if erased and active_displays_.size() == 1 (21c40: cmp x8, #0x1),
    //   requests IDisplayManager::registerCallbackWithEventMask(callback, 0) (21d08).
    DisplayAccessEffects revoke_tracking_service_access(
        std::int32_t calling_uid,
        bool permission_cache_granted,
        std::int32_t display_id) {
        std::lock_guard<std::mutex> lock(mutex_);
        if (!check_calling_permission(calling_uid, permission_cache_granted)) {
            return {DisplayAccessStatus::PermissionDenied, main_display_focus_, false, std::nullopt};
        }
        if (display_id == 0) {
            main_display_focus_ = false;
            return {DisplayAccessStatus::Allowed, main_display_focus_, false, std::nullopt};
        }
        return revoke_secondary_display_locked(display_id);
    }

    // ConnectionManager::DisplayManagerCallback::onDisplayEvent (0x182e0):
    // Only when event == 3 (182f8: cmp w2, #0x3), calls ConnectionManager::revokeTrackingServiceAccess(display_id).
    // Does NOT touch FocusPolicy::main_display_focus_ even if display_id == 0.
    DisplayAccessEffects on_display_event(std::int32_t display_id, std::int32_t event) {
        std::lock_guard<std::mutex> lock(mutex_);
        if (event != kDisplayRemovedEvent || display_id == 0) {
            return {DisplayAccessStatus::Allowed, main_display_focus_, false, std::nullopt};
        }
        return revoke_secondary_display_locked(display_id);
    }

    // ConnectionManager::onForegroundActivitiesChanged (0x20cc0):
    // Classifies matching_displays returned by getDisplaysWithTopActivities(pid, active_displays_):
    // - on_main_display = std::find(matching.begin(), matching.end(), 0) != matching.end()
    // - on_secondary_display = on_main_display ? (matching.size() > 1) : !matching.empty()
    // Updates:
    // - foreground_activities_ (+0x70): foreground_activities && on_main_display
    // - top_activity_clients_ (+0xf0): foreground_activities && (on_main_display || on_secondary_display)
    // - all_top_activity_clients_ (+0x130): foreground_activities
    ForegroundActivityEffects on_foreground_activities_changed(
        Client client,
        bool foreground_activities,
        const std::vector<std::int32_t>& matching_displays) {
        std::lock_guard<std::mutex> lock(mutex_);
        const bool on_main_display =
            std::find(matching_displays.begin(), matching_displays.end(), 0) != matching_displays.end();
        const bool on_secondary_display =
            on_main_display ? (matching_displays.size() > 1) : !matching_displays.empty();

        const bool in_foreground_activities = foreground_activities && on_main_display;
        const bool in_top_activities =
            foreground_activities && (on_main_display || on_secondary_display);
        const bool in_all_top_activities = foreground_activities;

        const bool fg_changed = update_set(foreground_activities_, client, in_foreground_activities);
        const bool top_changed = update_set(top_activity_clients_, client, in_top_activities);
        const bool all_top_changed = update_set(all_top_activity_clients_, client, in_all_top_activities);

        return ForegroundActivityEffects{
            fg_changed,
            top_changed,
            all_top_changed,
            fg_changed,
            top_changed,
        };
    }

    // ConnectionManager::onForegroundServicesChanged (0x20860):
    // 20908: cmp w21, #0x0 -> inserts when service_types != 0, erases when 0.
    bool on_foreground_services_changed(Client client, std::int32_t service_types) {
        std::lock_guard<std::mutex> lock(mutex_);
        return update_set(foreground_panels_, client, service_types != 0);
    }

    bool main_display_focus() const {
        std::lock_guard<std::mutex> lock(mutex_);
        return main_display_focus_;
    }

    std::vector<std::int32_t> active_displays() const {
        std::lock_guard<std::mutex> lock(mutex_);
        return {active_displays_.begin(), active_displays_.end()};
    }

    std::vector<Client> clients_with_foreground_activity() const {
        std::lock_guard<std::mutex> lock(mutex_);
        return {foreground_activities_.begin(), foreground_activities_.end()};
    }

    std::vector<Client> clients_with_foreground_panel_service() const {
        std::lock_guard<std::mutex> lock(mutex_);
        return {foreground_panels_.begin(), foreground_panels_.end()};
    }

    std::vector<Client> clients_with_top_activities() const {
        std::lock_guard<std::mutex> lock(mutex_);
        return {top_activity_clients_.begin(), top_activity_clients_.end()};
    }

    std::vector<Client> all_clients_with_top_activities() const {
        std::lock_guard<std::mutex> lock(mutex_);
        return {all_top_activity_clients_.begin(), all_top_activity_clients_.end()};
    }

private:
    static bool update_set(std::set<Client>& set, Client client, bool present) {
        if (present) {
            return set.insert(client).second;
        }
        return set.erase(client) > 0;
    }

    DisplayAccessEffects revoke_secondary_display_locked(std::int32_t display_id) {
        const bool erased = active_displays_.erase(display_id) > 0;
        std::optional<std::int32_t> mask;
        if (erased && active_displays_.size() == 1) {
            mask = kDisplayCallbackMaskNone;
        }
        return {DisplayAccessStatus::Allowed, main_display_focus_, erased, mask};
    }

    mutable std::mutex mutex_;
    bool main_display_focus_;
    std::set<std::int32_t> active_displays_;
    std::set<Client> foreground_activities_;
    std::set<Client> foreground_panels_;
    std::set<Client> top_activity_clients_;
    std::set<Client> all_top_activity_clients_;
};

} // namespace metaport::focus
