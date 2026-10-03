// SPDX-License-Identifier: GPL-3.0-only
#pragma once
#include "focus_decision.hpp"

namespace metaport::focus {
// Recovered addCurrentFocus/removeCurrentFocus bookkeeping, NOT permissions.
// Caller serializes access and installs records only from a trusted metadata
// backend. Queries/decisions never create records. No liveness is inferred here.
class CurrentFocusLedger final {
public:
    // Install a newly built/rebuilt metadata record, not a repeated lookup.
    // Replacement clears focus, including same-PID/same-UID process reuse.
    void install(Client client) { records_.insert_or_assign(client.pid, Record{client.uid,{}}); }
    void erase(Client client) {
        auto it=records_.find(client.pid);
        if (it!=records_.end() && it->second.uid==client.uid) records_.erase(it);
    }
    std::optional<std::set<FocusType>> current(Client client) const {
        const auto it=records_.find(client.pid);
        if (it==records_.end() || it->second.uid!=client.uid) return std::nullopt;
        return it->second.types;
    }
    void apply(const std::vector<FocusDecision>& decisions) {
        for (const auto& row:decisions)
            if (row.type!=FocusType::Type0 && row.type!=FocusType::Type1)
                throw std::invalid_argument("Invalid service focus type");
        for (const auto& row:decisions) {
            auto it=records_.find(row.identity.pid);
            // Native PID-indexed cache also checks UID before touching the set.
            if (it==records_.end() || it->second.uid!=row.identity.uid) continue;
            if (row.has_focus) it->second.types.insert(row.type);
            else it->second.types.erase(row.type);
        }
    }
    void swap(CurrentFocusLedger& other) noexcept { records_.swap(other.records_); }
private:
    struct Record { std::int32_t uid; std::set<FocusType> types; };
    std::map<std::int32_t,Record> records_;
};
} // namespace metaport::focus
