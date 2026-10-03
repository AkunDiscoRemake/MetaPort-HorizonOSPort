// SPDX-License-Identifier: GPL-3.0-only
#include "focus_decision.hpp"
#include <cassert>
#include <thread>
#include <algorithm>
#include <type_traits>
static_assert(!std::is_default_constructible_v<metaport::focus::DecisionInputs>);
using namespace metaport::focus;
static DecisionInputs empty() { return {{},{},{},{},std::nullopt,std::nullopt,std::nullopt,false}; }
static bool focused(const std::vector<FocusDecision>& rows,Client client) {
    const auto found=std::find_if(rows.begin(),rows.end(),[&](const auto& row){return row.identity==client;});
    assert(found!=rows.end());return found->has_focus;
}
int main() {
    const Client a{10,101},b{10,102},c{11,103},d{12,104},e{13,105},f{14,106};
    const std::vector<ClientMetadata> clients{{a,{}},{b,{}},{c,{}},{d,{}},{e,{}},{f,{}}};
    for (auto type:{FocusType::Type0,FocusType::Type1}) {
        auto denied=decide_focus(type,clients,empty());
        assert(denied.size()==clients.size());
        for (const auto& row:denied) {assert(!row.has_focus);assert(row.type==type);}
        assert(decide_focus(type,{},empty()).empty());
    }
    auto input=empty();input.foreground_activities={a,a};input.foreground_panels={b};
    input.connection_slot_5={c};input.connection_slot_6={d};input.window_focus=e;input.top_activity_client=f;
    for (const auto& row:decide_focus(FocusType::Type0,clients,input)) assert(row.has_focus);
    auto type1=decide_focus(FocusType::Type1,clients,input);
    for (auto client:{a,b,c}) assert(focused(type1,client));
    for (auto client:{d,e,f}) assert(!focused(type1,client));
    // Immersive main-display focus modifies only type 1, even if already eligible.
    input.immersive_pid=a.pid;
    assert(!focused(decide_focus(FocusType::Type1,clients,input),a));
    assert(focused(decide_focus(FocusType::Type0,clients,input),a));
    input.main_display_focus=true;
    assert(focused(decide_focus(FocusType::Type1,clients,input),a));
    input=empty();input.immersive_pid=b.pid;input.main_display_focus=true;
    assert(focused(decide_focus(FocusType::Type1,clients,input),b));
    input.immersive_pid=999;
    for (const auto& row:decide_focus(FocusType::Type1,clients,input)) assert(!row.has_focus);
    // Authorized background access is later than removal; it is type-specific.
    std::vector<ClientMetadata> grants{{a,{FocusType::Type1}},{b,{FocusType::Type0}}};
    input=empty();input.foreground_activities={a};input.immersive_pid=a.pid;
    assert(focused(decide_focus(FocusType::Type1,grants,input),a));
    assert(!focused(decide_focus(FocusType::Type1,grants,input),b));
    input=empty();assert(focused(decide_focus(FocusType::Type0,grants,input),b));
    assert(!focused(decide_focus(FocusType::Type0,grants,input),a));
    // First duplicate metadata wins; ordering is UID/PID, not request order/PID alone.
    const Client low{-1,500},high{15,1};
    auto ordered=decide_focus(FocusType::Type0,{{high,{}},{a,{}},{low,{}},{a,{FocusType::Type0}}},empty());
    assert(ordered.size()==3);assert(ordered[0].identity==low);assert(ordered[1].identity==a);
    assert(ordered[2].identity==high);assert(!ordered[1].has_focus);
    // Same PID with different resolved UIDs: only first matching identity adjusted.
    const Client reused{20,a.pid};input=empty();input.immersive_pid=a.pid;input.main_display_focus=true;
    auto reused_rows=decide_focus(FocusType::Type1,{{reused,{}},{a,{}}},input);
    assert(focused(reused_rows,a));assert(!focused(reused_rows,reused));
    // A PID match without its UID is never enough for membership.
    input=empty();input.foreground_activities={reused};
    assert(!focused(decide_focus(FocusType::Type0,{{a,{}}},input),a));
    for (int type:{-1,2,7}) {
        bool rejected=false;
        try { (void)decide_focus(static_cast<FocusType>(type),clients,input); }
        catch(const std::invalid_argument&) { rejected=true; }
        assert(rejected);
    }
    // Concurrent read-only computations must not mutate input or retain state.
    const auto stable=input;
    const auto run=[&]{for(int i=0;i<2000;++i) {
        auto rows=decide_focus(FocusType::Type0,clients,stable);
        assert(rows.size()==clients.size());for(const auto& row:rows) assert(!row.has_focus);
    }};
    std::thread t1(run),t2(run);run();t1.join();t2.join();
    assert(stable.foreground_activities.size()==1);
}
