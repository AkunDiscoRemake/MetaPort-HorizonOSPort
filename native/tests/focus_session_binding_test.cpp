// SPDX-License-Identifier: GPL-3.0-only
#include "focus_session_binding.hpp"
#include <cassert>
using namespace metaport::focus;
static packet::Request request() {
    return {true,false,FocusType::Type1,{},{{{10,100},{}}},
        DecisionInputs{{},{},{},{},std::nullopt,std::nullopt,std::nullopt,true},
        ImmersiveInputs{{},{{{10,100},"fixture","ordinary","fixture"}},{},"fixture"}};
}
static void reject(packet::Request value) {
    bool rejected=false;
    try { bind_own_session_rendering(value,{10,100},true); }
    catch (const std::invalid_argument&) { rejected=true; }
    assert(rejected);
}
int main() {
    const Client own{10,100};FocusPolicyCore core;core.install_client_record(own);
    auto visible=request();bind_own_session_rendering(visible,own,true);
    assert(visible.immersive.rendering.size()==1);
    assert(visible.decisions.foreground_activities.empty());
    assert(visible.decisions.foreground_panels.empty());
    auto result=core.evaluate(visible.type,visible.requested,visible.immersive,visible.decisions,visible.timestamp);
    assert(result.immersive && result.decisions[0].has_focus);
    auto stopped=request();bind_own_session_rendering(stopped,own,false);
    assert(stopped.immersive.live_metadata.size()==1 && stopped.immersive.rendering.empty());
    result=core.evaluate(stopped.type,stopped.requested,stopped.immersive,stopped.decisions,stopped.timestamp);
    assert(!result.immersive && !result.decisions[0].has_focus);
    auto value=request();value.session_rendering=false;reject(value);
    value=request();value.immersive.rendering=value.immersive.live_metadata;reject(value);
    value=request();value.immersive.live_metadata.clear();reject(value);
    value=request();value.immersive.live_metadata.push_back(value.immersive.live_metadata[0]);reject(value);
    value=request();value.requested[0].identity.uid=11;reject(value);
    for(int i=0;i<4;i++) {
        value=request();
        std::vector<Client>* feeds[]={&value.decisions.foreground_activities,&value.decisions.foreground_panels,
                       &value.decisions.top_activity_clients,&value.decisions.all_top_activity_clients};
        feeds[i]->push_back({11,100});reject(value);
    }
    value=request();value.decisions.window_focus=Client{10,101};reject(value);
    value=request();value.immersive.live_metadata[0].identity.pid=101;reject(value);
    value=request();value.immersive.foreground_metadata.push_back(value.immersive.live_metadata[0]);
    value.immersive.foreground_metadata[0]->process_name_for_top="inconsistent";reject(value);
    value=request();value.immersive.foreground_metadata={std::nullopt,value.immersive.live_metadata[0]};
    bind_own_session_rendering(value,own,true);
    // Parsing preserves the delegation tag; it is not an asserted empty feed.
    packet::Writer writer;writer.integer(packet::session_request_magic);writer.integer(1);writer.timestamp({});
    writer.integer(0); // requested
    for(int i=0;i<4;i++) writer.integer(0); // independent identity feeds
    writer.integer(0);writer.integer(1); // window absent/display focus
    writer.integer(0);writer.integer(0);writer.integer(0);writer.text("");
    auto parsed=packet::decode(writer.bytes);assert(parsed.session_rendering);reject(parsed);
}
