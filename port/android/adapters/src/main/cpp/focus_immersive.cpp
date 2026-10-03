// SPDX-License-Identifier: GPL-3.0-only
#include "focus_immersive.hpp"

namespace metaport::focus {
PolicyEvaluation FocusPolicyCore::evaluate(FocusType type, const std::vector<ClientMetadata>& requested,
                              const ImmersiveInputs& immersive, DecisionInputs inputs,
                              std::chrono::system_clock::time_point observed_at) {
        std::lock_guard<std::mutex> lock(mutex_);
        const auto top=top_activity_client(immersive);
        auto selected=select_immersive(immersive,inputs.window_focus);
        // Selection, not an externally supplied/default PID, drives this input.
        inputs.top_activity_client=top ? std::optional<Client>(top->identity) : std::nullopt;
        inputs.immersive_pid=selected ? std::optional<std::int32_t>(selected->identity.pid) : std::nullopt;
        auto rows=decide_focus(type,requested,inputs); // Reject invalid types before state changes.
        PolicyEvaluation evaluation{top ? top->package_name : immersive.primary_display_top,
                                    selected,std::move(rows)};
        // Native history compares PID ONLY, not package/UID/top flag. Empty
        // selections aren't recorded; a gap doesn't reset the previous history PID.
        if (selected && (history_.empty() || history_.front().app.identity.pid!=selected->identity.pid)) {
            history_.push_front({observed_at,*selected});
            if (history_.size()>10) history_.pop_back();
        }
        current_=std::move(selected);
        return evaluation;
    }
std::optional<ImmersiveApp> FocusPolicyCore::current() const {
        std::lock_guard<std::mutex> lock(mutex_);return current_;
    }
std::vector<ImmersiveHistoryRecord> FocusPolicyCore::history() const {
        std::lock_guard<std::mutex> lock(mutex_);return {history_.begin(),history_.end()};
    }
} // namespace metaport::focus
