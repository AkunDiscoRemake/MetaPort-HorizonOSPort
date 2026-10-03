// SPDX-License-Identifier: GPL-3.0-only
#pragma once
#include "focus_current.hpp"
#include "focus_decision.hpp"
#include <chrono>
#include <deque>
#include <string>

namespace metaport::focus {
struct ImmersiveClient {
    Client identity;
    std::string package_name;
    std::string metadata_process_name;
    // Result of original Process::getProcessName(pid, true), not a guessed
    // package/component name. Its observation/normalization backend is unported.
    std::string process_name_for_top;
};
struct ImmersiveApp {
    Client identity;
    std::string package_name;
    bool is_top_activity;
};
struct ImmersiveInputs {
    ImmersiveInputs(std::vector<ImmersiveClient> rendering,
                    std::vector<ImmersiveClient> live_metadata,
                    std::vector<std::optional<ImmersiveClient>> foreground_metadata,
                    std::string primary_display_top)
        : rendering(std::move(rendering)), live_metadata(std::move(live_metadata)),
          foreground_metadata(std::move(foreground_metadata)),
          primary_display_top(std::move(primary_display_top)) {}
    // Original rendering order, after live-process filtering and successful lookups.
    std::vector<ImmersiveClient> rendering;
    // Original getSnapshot prunes dead processes before returning this metadata.
    std::vector<ImmersiveClient> live_metadata;
    // Lookup results in foreground activity order; nullopt means lookup failed.
    std::vector<std::optional<ImmersiveClient>> foreground_metadata;
    std::string primary_display_top;
};
inline bool has_top_activity_exception(const std::string& process) {
    return process=="system_server" || process=="com.oculus.vralertservice" ||
           process=="com.oculus.os.vrlockscreen" || process=="com.android.settings";
}
inline std::optional<ImmersiveClient> top_activity_client(const ImmersiveInputs& inputs) {
    for (auto it=inputs.foreground_metadata.rbegin();it!=inputs.foreground_metadata.rend();++it)
        if (*it) return **it;
    return std::nullopt;
}
inline std::string top_activity_name(const ImmersiveInputs& inputs) {
    auto client=top_activity_client(inputs);
    return client ? client->package_name : inputs.primary_display_top;
}
inline std::optional<ImmersiveApp> package_as_immersive(
        const std::vector<ImmersiveClient>& live_metadata,
        const std::string& package, const std::string& top_name) {
    std::map<Client,ImmersiveClient> ordered;
    for (const auto& client:live_metadata) ordered.emplace(client.identity,client);
    for (const auto& [identity,client]:ordered)
        if (client.package_name==package)
            return ImmersiveApp{identity,client.package_name,client.process_name_for_top==top_name};
    return std::nullopt;
}
// Reconstructed stable-snapshot selection, not an observer of Android/XR state.
inline std::optional<ImmersiveApp> select_immersive(
        const ImmersiveInputs& inputs, std::optional<Client> window_focus) {
    // Two passes are essential: a window-matching exception outranks an earlier
    // exception in the rendering list. Native compares the PID only in pass one.
    if (window_focus) for (const auto& client:inputs.rendering)
        if (client.identity.pid==window_focus->pid && has_top_activity_exception(client.metadata_process_name))
            return ImmersiveApp{client.identity,client.package_name,true};
    for (const auto& client:inputs.rendering)
        if (has_top_activity_exception(client.metadata_process_name))
            return ImmersiveApp{client.identity,client.package_name,true};
    const std::string top=top_activity_name(inputs);
    auto shell=package_as_immersive(inputs.live_metadata,"com.oculus.vrshell",top);
    if (shell && (shell->is_top_activity || top=="com.oculus.vrshell")) {
        shell->is_top_activity=true;
        return shell;
    }
    for (const auto& client:inputs.rendering)
        if (client.process_name_for_top==top)
            return ImmersiveApp{client.identity,client.package_name,true};
    return std::nullopt; // Never retain the previous app simply because it is alive.
}
struct ImmersiveHistoryRecord {
    std::chrono::system_clock::time_point timestamp;
    ImmersiveApp app;
};
struct PolicyEvaluation {
    std::string top_activity;
    std::optional<ImmersiveApp> immersive;
    std::vector<FocusDecision> decisions;
};

// Combines selection with the decision kernel and bounded diagnostic history.
// Still requires trustworthy, coherent inputs; no Binder publication, synthetic
// observations or process-liveness probing. Bookkeeping only touches explicitly
// installed records; the real metadata provider remains unimplemented.
class FocusPolicyCore final {
public:
    PolicyEvaluation evaluate(FocusType type, const std::vector<ClientMetadata>& requested,
                              const ImmersiveInputs& immersive, DecisionInputs inputs,
                              std::chrono::system_clock::time_point observed_at);
    void install_client_record(Client client);
    void erase_client_record(Client client);
    std::optional<std::set<FocusType>> current_focus(Client client) const;
    std::optional<ImmersiveApp> current() const;
    std::vector<ImmersiveHistoryRecord> history() const;

private:
    mutable std::mutex mutex_;
    CurrentFocusLedger focus_;
    std::optional<ImmersiveApp> current_;
    std::deque<ImmersiveHistoryRecord> history_;
};
} // namespace metaport::focus
