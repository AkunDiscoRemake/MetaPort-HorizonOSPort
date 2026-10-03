// SPDX-License-Identifier: GPL-3.0-only
#pragma once
#include <cstdint>
#include <mutex>
#include <optional>
#include <set>
#include <tuple>
#include <vector>

namespace metaport::focus {
// Observed vrfocus service codes, NOT XrSessionState numeric values.
enum class ServiceAppState : std::int32_t { Visible = 0, Stopping = 2 };

struct Client {
    std::int32_t uid;
    std::int32_t pid;
    bool operator<(const Client& other) const {
        return std::tie(uid, pid) < std::tie(other.uid, other.pid);
    }
    bool operator==(const Client& other) const { return uid == other.uid && pid == other.pid; }
};

enum class Access { Allowed, CallingPidMismatch };
struct Effects {
    Access access = Access::Allowed;
    bool membership_changed = false;
    bool refresh_activity_state = false;
    bool notify_top_activity = false;
    bool report_immersive_app_update = false;
};

// Project implementation of the recovered state reducer, not a Binder service.
// Caller identity and observed_uid must come from a trusted process backend,
// never a caller-supplied UID. No clients, poses, focus grants or providers are seeded.
// Evidence: original vrfocusserver 0x2c450, 0x22510, 0x20a60; see FOCUS-NATIVE.md.
class SessionState final {
public:
    Effects apply(std::int32_t calling_pid, std::int32_t requested_pid,
                  std::optional<std::int32_t> observed_uid, std::int32_t service_state) {
        if (calling_pid != requested_pid) return {Access::CallingPidMismatch};
        // Original obtains process UID and calls optional::value even for ignored states.
        const Client client{observed_uid.value(), requested_pid};
        Effects effects;
        std::lock_guard<std::mutex> lock(mutex_);
        if (service_state == static_cast<std::int32_t>(ServiceAppState::Visible)) {
            effects.membership_changed = visible_.insert(client).second;
        } else if (service_state == static_cast<std::int32_t>(ServiceAppState::Stopping)) {
            effects.membership_changed = visible_.erase(client) != 0;
            effects.refresh_activity_state = true;
        } else {
            return effects; // Do not reinterpret other OpenXR or service state numbers.
        }
        // Original service emits these effects even for duplicate visible/stop events.
        effects.notify_top_activity = true;
        effects.report_immersive_app_update = true;
        return effects;
    }

    bool contains(Client client) const {
        std::lock_guard<std::mutex> lock(mutex_);
        return visible_.count(client)!=0;
    }

    std::vector<Client> snapshot() const {
        std::lock_guard<std::mutex> lock(mutex_);
        return {visible_.begin(), visible_.end()};
    }
private:
    mutable std::mutex mutex_;
    std::set<Client> visible_;
};
} // namespace metaport::focus
