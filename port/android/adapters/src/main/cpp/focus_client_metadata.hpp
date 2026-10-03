// SPDX-License-Identifier: GPL-3.0-only
#pragma once
#include "focus_immersive.hpp"
#include <algorithm>
#include <array>
#include <cstdint>
#include <map>
#include <mutex>
#include <optional>
#include <set>
#include <string>
#include <string_view>
#include <utility>
#include <vector>

namespace metaport::focus {

// Recovered from _GLOBAL__sub_I_ClientManager.cpp (0xf0d0).
inline constexpr std::string_view kBackgroundHeadPermission =
    "horizonos.permission.ACCESS_BACKGROUND_HEAD_TRACKING";
inline constexpr std::string_view kBackgroundInputPermission =
    "horizonos.permission.ACCESS_BACKGROUND_INPUT_TRACKING";

inline constexpr std::array<std::string_view, 3> kAllowlistedBackgroundPackages = {
    "com.oculus.vrshell",
    "com.oculus.guardian",
    "com.oculus.systemdriver",
};

struct DaemonAllowlistEntry {
    std::string_view binary_path;
    std::int32_t uid;
};

inline constexpr std::array<DaemonAllowlistEntry, 2> kAllowlistedBackgroundDaemons = {{
    {"/system/bin/audioserver", 1041},
    {"/system_ext/bin/mrsystemservice", 1000},
}};

inline constexpr std::string_view kSystemServerProcessName = "system_server";
inline constexpr std::string_view kSystemServerPackageName = "android.uid.system:1000";

struct ClientProcessObservation {
    std::int32_t pid = 0;
    std::optional<std::int32_t> uid{};
    // Result of Process::getProcessName(pid, true) at 0x10c04 / 0x11a60.
    std::string process_name_true{};
    // Result of AppOpsWrapper::getPackagesForUid(*uid) at 0x10c1c.
    std::vector<std::string> packages_for_uid{};
    // Result of checkPermission(..., pid, *uid) at 0x11108.
    bool has_background_head_permission = false;
    bool has_background_input_permission = false;
};

struct ClientMetadataRecord {
    Client identity{};
    std::string package_name{};
    std::string metadata_process_name{};
    std::set<FocusType> allowed_background_focus{};
    std::set<FocusType> current_focus{};

    int allowed_background_mask() const {
        int mask = 0;
        for (FocusType type : allowed_background_focus) {
            mask |= 1 << static_cast<int>(type);
        }
        return mask;
    }

    int current_focus_mask() const {
        int mask = 0;
        for (FocusType type : current_focus) {
            mask |= 1 << static_cast<int>(type);
        }
        return mask;
    }

    ClientMetadata to_client_metadata() const {
        return ClientMetadata{identity, allowed_background_focus};
    }

    ImmersiveClient to_immersive_client(std::string process_name_for_top) const {
        return ImmersiveClient{
            identity,
            package_name,
            metadata_process_name,
            std::move(process_name_for_top),
        };
    }

    bool operator==(const ClientMetadataRecord& other) const {
        return identity == other.identity &&
               package_name == other.package_name &&
               metadata_process_name == other.metadata_process_name &&
               allowed_background_focus == other.allowed_background_focus &&
               current_focus == other.current_focus;
    }
};

// Recovered from OVR::OS::ClientManager::buildClientInfo(int) at 0x10aa0.
inline std::string c_str_prefix_metadata(std::string_view value) {
    return std::string(value.substr(0, value.find('\0')));
}

inline std::optional<ClientMetadataRecord> resolve_client_metadata(
    const ClientProcessObservation& observation) {
    if (!observation.uid.has_value()) {
        return std::nullopt;
    }
    const std::int32_t uid = *observation.uid;
    ClientMetadataRecord record;
    record.identity = Client{uid, observation.pid};
    record.metadata_process_name = observation.process_name_true;

    // 0x10cb8..0x10fd8: single-package UID vs multi-package UID disambiguation.
    if (observation.packages_for_uid.size() == 1) {
        // String8(String16) -> std::string(const char*) truncates at first NUL.
        record.package_name = c_str_prefix_metadata(observation.packages_for_uid[0]);
    } else if (observation.packages_for_uid.size() >= 2) {
        const std::size_t colon = record.metadata_process_name.find(':', 0);
        const std::string prefix = record.metadata_process_name.substr(0, colon);
        // String16(prefix.c_str()) compared via strzcmp16 against each UID package.
        const std::string base = c_str_prefix_metadata(prefix);
        for (const std::string& candidate : observation.packages_for_uid) {
            if (c_str_prefix_metadata(candidate) == base) {
                // 0x10f48..0x10f4c: copies local_78 (full metadata_process_name,
                // including any ":suffix") into record.package_name.
                record.package_name = record.metadata_process_name;
                break;
            }
        }
    }

    // 0x10fdc..0x11084: "system_server" overrides package_name to "android.uid.system:1000".
    if (record.metadata_process_name == kSystemServerProcessName) {
        record.package_name = std::string(kSystemServerPackageName);
    }

    // 0x11088..0x1122c: root (uid == 0) or granted background focus permissions.
    if (uid == 0 || observation.has_background_head_permission) {
        record.allowed_background_focus.insert(FocusType::Type0);
    }
    if (uid == 0 || observation.has_background_input_permission) {
        record.allowed_background_focus.insert(FocusType::Type1);
    }

    // 0x11230..0x11360: allowlisted system packages receive {Type0, Type1}.
    for (std::string_view allowlisted_pkg : kAllowlistedBackgroundPackages) {
        if (record.package_name == allowlisted_pkg) {
            record.allowed_background_focus.insert(FocusType::Type0);
            record.allowed_background_focus.insert(FocusType::Type1);
            break;
        }
    }

    // 0x11360..0x114a8: allowlisted native daemons matching both path and UID receive {Type0, Type1}.
    for (const DaemonAllowlistEntry& daemon : kAllowlistedBackgroundDaemons) {
        if (record.metadata_process_name == daemon.binary_path && uid == daemon.uid) {
            record.allowed_background_focus.insert(FocusType::Type0);
            record.allowed_background_focus.insert(FocusType::Type1);
            break;
        }
    }

    return record;
}

// Recovered PID-indexed ClientManager cache (0x10aa0, 0x118e0, 0x12bc0, 0x12de0, 0x13400).
class ClientMetadataCache {
public:
    // OVR::OS::ClientManager::getClientInfo(FocusClient const&) at 0x118e0.
    // On UID match: copies cached record and refreshes copy.metadata_process_name
    // from Process::getProcessName(pid, true) without mutating the map entry.
    // On UID mismatch: erases the stale PID entry from the cache and returns nullopt.
    std::optional<ClientMetadataRecord> get_client_info(
        Client client,
        std::string refreshed_process_name_true) {
        std::lock_guard<std::mutex> lock(mutex_);
        auto it = by_pid_.find(client.pid);
        if (it == by_pid_.end()) {
            return std::nullopt;
        }
        if (it->second.identity.uid != client.uid) {
            by_pid_.erase(it);
            return std::nullopt;
        }
        ClientMetadataRecord copy = it->second;
        copy.metadata_process_name = std::move(refreshed_process_name_true);
        return copy;
    }

    // OVR::OS::ClientManager::buildClientInfo(int) at 0x10aa0.
    // Resolves UID, returns getClientInfo({*uid, pid}) on cache hit (or evicts
    // a stale UID entry via getClientInfo), and otherwise builds and caches a
    // fresh record keyed by PID.
    std::optional<ClientMetadataRecord> build_client_info(
        const ClientProcessObservation& observation) {
        if (!observation.uid.has_value()) {
            return std::nullopt;
        }
        const Client identity{*observation.uid, observation.pid};
        if (auto cached = get_client_info(identity, observation.process_name_true)) {
            return cached;
        }
        auto built = resolve_client_metadata(observation);
        if (!built.has_value()) {
            return std::nullopt;
        }
        std::lock_guard<std::mutex> lock(mutex_);
        by_pid_.emplace(observation.pid, *built);
        return built;
    }

    // OVR::OS::ClientManager::addCurrentFocus(FocusClient const&, FocusType) at 0x12bc0.
    bool add_current_focus(Client client, FocusType type) {
        std::lock_guard<std::mutex> lock(mutex_);
        auto it = by_pid_.find(client.pid);
        if (it == by_pid_.end() || it->second.identity.uid != client.uid) {
            return false;
        }
        it->second.current_focus.insert(type);
        return true;
    }

    // OVR::OS::ClientManager::removeCurrentFocus(FocusClient const&, FocusType) at 0x12de0.
    bool remove_current_focus(Client client, FocusType type) {
        std::lock_guard<std::mutex> lock(mutex_);
        auto it = by_pid_.find(client.pid);
        if (it == by_pid_.end() || it->second.identity.uid != client.uid) {
            return false;
        }
        it->second.current_focus.erase(type);
        return true;
    }

    // OVR::OS::ClientManager::getSnapshot() at 0x13400.
    // Prunes entries where !is_process_alive(pid) under mutex_ and returns the
    // surviving records ordered by ClientIdentity (uid, then pid).
    template <typename IsAliveFn>
    std::vector<ClientMetadataRecord> get_snapshot(IsAliveFn&& is_process_alive) {
        std::lock_guard<std::mutex> lock(mutex_);
        std::vector<ClientMetadataRecord> result;
        for (auto it = by_pid_.begin(); it != by_pid_.end();) {
            if (!is_process_alive(it->first)) {
                it = by_pid_.erase(it);
            } else {
                result.push_back(it->second);
                ++it;
            }
        }
        std::sort(result.begin(), result.end(),
                  [](const ClientMetadataRecord& a, const ClientMetadataRecord& b) {
                      return a.identity < b.identity;
                  });
        return result;
    }

    std::optional<ClientMetadataRecord> peek_cached_for_pid(std::int32_t pid) const {
        std::lock_guard<std::mutex> lock(mutex_);
        auto it = by_pid_.find(pid);
        if (it == by_pid_.end()) {
            return std::nullopt;
        }
        return it->second;
    }

    std::size_t size() const {
        std::lock_guard<std::mutex> lock(mutex_);
        return by_pid_.size();
    }

private:
    mutable std::mutex mutex_;
    std::map<std::int32_t, ClientMetadataRecord> by_pid_;
};

} // namespace metaport::focus
