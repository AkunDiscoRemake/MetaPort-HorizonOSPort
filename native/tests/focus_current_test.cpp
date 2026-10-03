// SPDX-License-Identifier: GPL-3.0-only
#include "focus_immersive.hpp"
#include <cassert>
#include <thread>
using namespace metaport::focus;
int main() {
    const Client a{10,100}, reused{11,100}, b{10,101};
    const auto t0=FocusType::Type0, t1=FocusType::Type1;
    CurrentFocusLedger ledger;
    ledger.apply({{a,t0,true}});assert(!ledger.current(a));
    ledger.install(a);ledger.install(b);
    ledger.apply({{reused,t0,true}});assert(ledger.current(a)->empty());
    ledger.apply({{a,t0,true},{a,t1,true},{a,t0,true},{b,t0,true}});
    assert(ledger.current(a)->size()==2);
    ledger.apply({{a,t0,false},{a,t0,false}});
    assert(*ledger.current(a)==std::set<FocusType>{t1});
    assert(*ledger.current(b)==std::set<FocusType>{t0});
    ledger.erase(reused);assert(ledger.current(a));
    ledger.install(reused);assert(!ledger.current(a));assert(ledger.current(reused)->empty());
    ledger.apply({{a,t1,true},{reused,t0,true}});
    assert(*ledger.current(reused)==std::set<FocusType>{t0});
    ledger.install(reused);assert(ledger.current(reused)->empty());
    ledger.erase(reused);assert(!ledger.current(reused));
    bool rejected=false;
    try {ledger.apply({{b,t0,false},{b,static_cast<FocusType>(2),true}});}
    catch (const std::invalid_argument&) {rejected=true;}
    assert(rejected);assert(*ledger.current(b)==std::set<FocusType>{t0});
    FocusPolicyCore core;
    auto evaluate=[&](FocusType type,bool eligible) {
        DecisionInputs input{{},{},{},{},std::nullopt,std::nullopt,std::nullopt,false};
        if (eligible) input.foreground_activities={a,b};
        return core.evaluate(type,{{a,{}},{b,{}}},ImmersiveInputs{{},{},{},""},input,{});
    };
    assert(evaluate(t0,true).decisions.size()==2);
    assert(!core.current_focus(a)); // Decisions cannot invent metadata records.
    core.install_client_record(a);core.install_client_record(b);
    evaluate(t0,true);evaluate(t1,true);
    assert(core.current_focus(a)->size()==2);
    // Reinstalling clears the record; an identical query must commit it again.
    core.install_client_record(a);evaluate(t1,true);
    assert(*core.current_focus(a)==std::set<FocusType>{t1});
    evaluate(t1,false);assert(core.current_focus(a)->empty());
    auto copy=core.current_focus(b);copy->clear();
    assert(*core.current_focus(b)==std::set<FocusType>{t0});
    rejected=false;
    try {evaluate(static_cast<FocusType>(-1),true);}
    catch (const std::invalid_argument&) {rejected=true;}
    assert(rejected);assert(core.current_focus(a)->empty());
    std::thread writer([&]{for(int i=0;i<500;++i) evaluate(t0,i%2==0);});
    std::thread lifecycle([&]{for(int i=0;i<500;++i) {
        core.erase_client_record(a);core.install_client_record(a);
    }});
    std::thread reader([&]{for(int i=0;i<500;++i) {
        auto state=core.current_focus(a);
        if(state) assert(state->size()<=1);
    }});
    writer.join();lifecycle.join();reader.join();
    evaluate(t0,true);assert(*core.current_focus(a)==std::set<FocusType>{t0});
    core.erase_client_record(a);assert(!core.current_focus(a));
}
