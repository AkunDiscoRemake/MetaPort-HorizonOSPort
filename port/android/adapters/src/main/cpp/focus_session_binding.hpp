// SPDX-License-Identifier: GPL-3.0-only
#pragma once
#include "focus_policy_packet.hpp"

namespace metaport::focus {
// Called while the JNI registry lock excludes session changes and destruction.
// Session membership feeds ONLY rendering (ConnectionManager +0x170). All other
// observations and resolved metadata are still required from the trusted producer.
inline void bind_own_session_rendering(packet::Request& request,Client own,bool visible) {
    packet::require(request.session_rendering && request.immersive.rendering.empty());
    const auto check=[own](Client value) { packet::require(value==own); };
    for (const auto& row:request.requested) check(row.identity);
    for (const auto* feed:{&request.decisions.foreground_activities,&request.decisions.foreground_panels,
                          &request.decisions.top_activity_clients,&request.decisions.all_top_activity_clients})
        for (const auto& client:*feed) check(client);
    if (request.decisions.window_focus) check(*request.decisions.window_focus);
    packet::require(request.immersive.live_metadata.size()==1);
    const auto& metadata=request.immersive.live_metadata.front();check(metadata.identity);
    for (const auto& row:request.immersive.foreground_metadata) if (row) {
        check(row->identity);
        packet::require(row->package_name==metadata.package_name &&
                        row->metadata_process_name==metadata.metadata_process_name &&
                        row->process_name_for_top==metadata.process_name_for_top);
    }
    // No permission, foreground/window state, main-display focus or top name is
    // inferred from this event. Stopping does not erase live process metadata.
    if (visible) request.immersive.rendering.push_back(metadata);
}
} // namespace metaport::focus
