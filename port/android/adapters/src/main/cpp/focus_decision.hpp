// SPDX-License-Identifier: GPL-3.0-only
#pragma once
#include "focus_session_state.hpp"
#include <map>
#include <stdexcept>
#include <utility>

namespace metaport::focus {
// Numeric values recovered from the service; NOT OpenXR session states.
enum class FocusType : std::int32_t { Type0 = 0, Type1 = 1 };
struct ClientMetadata {
    Client identity;
    // Must originate in the real permission/metadata backend, never manifest
    // wishes or caller-supplied grants. Original metadata offset +0x38.
    std::set<FocusType> background_access;
};
struct DecisionInputs {
    // No default constructor: all input channels and the display-focus state
    // must be supplied deliberately. A missing backend is not an empty feed.
    DecisionInputs(std::vector<Client> activities, std::vector<Client> panels,
                   std::vector<Client> top_clients, std::vector<Client> all_top_clients,
                   std::optional<Client> window, std::optional<Client> top,
                   std::optional<std::int32_t> immersive, bool display_focus)
        : foreground_activities(std::move(activities)), foreground_panels(std::move(panels)),
          top_activity_clients(std::move(top_clients)), all_top_activity_clients(std::move(all_top_clients)),
          window_focus(window), top_activity_client(top), immersive_pid(immersive),
          main_display_focus(display_focus) {}

    std::vector<Client> foreground_activities;
    std::vector<Client> foreground_panels;
    // Exact slots 5/6 verified in native recovery run 37121195806.
    // These are distinct observed sets; do not alias one to the other.
    std::vector<Client> top_activity_clients;
    std::vector<Client> all_top_activity_clients;
    std::optional<Client> window_focus;
    std::optional<Client> top_activity_client;
    std::optional<std::int32_t> immersive_pid;
    bool main_display_focus;
};
struct FocusDecision {
    Client identity;
    FocusType type;
    bool has_focus;
    // Every row also requests the original ClientManager focus gained/lost
    // bookkeeping, including repeated queries. Caller must apply it in order.
};

// Executable decision kernel recovered from computeFocusState (0x25460),
// not a full FocusPolicy, permission backend, Binder provider or sensor grant.
// resolved_requests contains only successful original getClientInfo lookups.
// Inputs are a trusted coherent snapshot; unavailable feeds must NOT be passed
// as empty observations. No backend produces this complete snapshot yet.
inline std::vector<FocusDecision> decide_focus(
        FocusType type, const std::vector<ClientMetadata>& resolved_requests,
        const DecisionInputs& inputs) {
    if (type != FocusType::Type0 && type != FocusType::Type1)
        throw std::invalid_argument("Invalid service focus type");
    // getClientSet orders by signed UID then PID, deduplicating exact identities
    // and preserving the first metadata record for duplicates.
    std::map<Client, ClientMetadata> clients;
    for (const auto& client : resolved_requests) clients.emplace(client.identity, client);
    std::set<Client> eligible;
    const auto add = [&eligible](const std::vector<Client>& source) {
        eligible.insert(source.begin(), source.end());
    };
    add(inputs.foreground_activities);
    add(inputs.foreground_panels);
    add(inputs.top_activity_clients);
    if (type == FocusType::Type0) {
        if (inputs.window_focus) eligible.insert(*inputs.window_focus);
        if (inputs.top_activity_client) eligible.insert(*inputs.top_activity_client);
        add(inputs.all_top_activity_clients);
    } else if (inputs.immersive_pid) {
        // Native code matches the immersive PID against the sorted queried
        // metadata, then uses THAT record's UID. Do not silently use an app UID.
        for (const auto& [identity, metadata] : clients) {
            (void)metadata;
            if (identity.pid != *inputs.immersive_pid) continue;
            if (inputs.main_display_focus) eligible.insert(identity);
            else eligible.erase(identity);
            break;
        }
    }
    // Background access is applied AFTER the immersive main-display adjustment.
    for (const auto& [identity, metadata] : clients)
        if (metadata.background_access.count(type)) eligible.insert(identity);
    std::vector<FocusDecision> result;
    result.reserve(clients.size());
    for (const auto& [identity, metadata] : clients) {
        (void)metadata;
        result.push_back({identity, type, eligible.count(identity) != 0});
    }
    // Deliberately no ro.debuggable/debug.ovr.vrfocus.permissive fallback.
    return result;
}
} // namespace metaport::focus
