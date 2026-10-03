// SPDX-License-Identifier: GPL-3.0-only
#include "focus_immersive.hpp"
#include <cassert>
#include <thread>
#include <type_traits>
using namespace metaport::focus;
static_assert(!std::is_default_constructible_v<ImmersiveInputs>);
static ImmersiveClient client(int uid,int pid,std::string package,std::string process="ordinary",
                              std::string name_for_top="ordinary") {
    return {{uid,pid},std::move(package),std::move(process),std::move(name_for_top)};
}
static ImmersiveInputs empty() { return {{},{},{},""}; }
static DecisionInputs base() {return {{},{},{},{},std::nullopt,std::nullopt,std::nullopt,false};}
int main() {
    const auto a=client(10,101,"a","ordinary","a");
    const auto alert=client(11,102,"alert","com.oculus.vralertservice","alert");
    const auto settings=client(12,103,"settings","com.android.settings","settings");
    for (const auto* exception:{"system_server","com.oculus.vralertservice","com.oculus.os.vrlockscreen","com.android.settings"})
        assert(has_top_activity_exception(exception));
    for (const auto* nonexception:{"", "System_server", "system_server:child", "com.android.settings.extra", "com.oculus.vrshell"})
        assert(!has_top_activity_exception(nonexception));
    auto inputs=empty();assert(!select_immersive(inputs,std::nullopt));
    inputs.foreground_metadata={a,std::nullopt,alert,std::nullopt};
    inputs.primary_display_top="fallback";
    assert(top_activity_client(inputs)->identity==alert.identity);
    assert(top_activity_name(inputs)=="alert");
    inputs.foreground_metadata={std::nullopt};assert(top_activity_name(inputs)=="fallback");
    // Exceptions outrank shell/top rendering, and the window matching exception wins.
    inputs.rendering={a,alert,settings};inputs.primary_display_top="a";
    assert(select_immersive(inputs,std::nullopt)->identity==alert.identity);
    auto picked=select_immersive(inputs,Client{999,settings.identity.pid});
    assert(picked->identity==settings.identity);assert(picked->is_top_activity);
    assert(select_immersive(inputs,a.identity)->identity==alert.identity);
    // Match exception PROCESS metadata, not the package name.
    inputs.rendering={client(10,200,"com.android.settings","ordinary","other")};
    assert(!select_immersive(inputs,std::nullopt));
    // Shell fallback queries the fixed package, not whichever package is on top.
    const auto shell=client(20,300,"com.oculus.vrshell","shell","com.oculus.vrshell:service");
    inputs=empty();inputs.live_metadata={shell,a};inputs.primary_display_top="com.oculus.vrshell";
    assert(select_immersive(inputs,std::nullopt)->identity==shell.identity);
    inputs.primary_display_top="com.oculus.vrshell:service";
    assert(select_immersive(inputs,std::nullopt)->identity==shell.identity);
    inputs.primary_display_top="a";
    assert(!select_immersive(inputs,std::nullopt));
    inputs.rendering={a};assert(select_immersive(inputs,std::nullopt)->identity==a.identity);
    // Equal package names resolve to the first UID/PID metadata record.
    auto lower_shell=shell;lower_shell.identity={19,999};
    auto package=package_as_immersive({shell,lower_shell},"com.oculus.vrshell","other");
    assert(package->identity==lower_shell.identity);assert(!package->is_top_activity);
    // Selection is wired into type-1 policy; forged supplied immersive/top inputs
    // are overwritten. Main-display false removes the actual selected candidate.
    FocusPolicyCore core;
    const std::vector<ClientMetadata> queried{{a.identity,{}},{alert.identity,{}}};
    auto decision=base();decision.foreground_activities={a.identity,alert.identity};
    decision.immersive_pid=alert.identity.pid;decision.top_activity_client=alert.identity;
    const auto now=std::chrono::system_clock::time_point{};
    auto evaluated=core.evaluate(FocusType::Type1,queried,inputs,decision,now);
    assert(evaluated.immersive->identity==a.identity);assert(evaluated.top_activity=="a");
    assert(!evaluated.decisions[0].has_focus);assert(evaluated.decisions[1].has_focus);
    assert(core.current()->identity==a.identity);assert(core.history().size()==1);
    // Repeated PID, even after an empty selection, doesn't append/update history.
    core.evaluate(FocusType::Type1,queried,inputs,decision,now+std::chrono::seconds(1));
    core.evaluate(FocusType::Type1,queried,empty(),decision,now+std::chrono::seconds(2));
    assert(!core.current());assert(core.history().size()==1);
    core.evaluate(FocusType::Type1,queried,inputs,decision,now+std::chrono::seconds(3));
    assert(core.history().size()==1);assert(core.history()[0].timestamp==now);
    inputs.rendering[0].identity.uid=99;
    core.evaluate(FocusType::Type1,queried,inputs,decision,now);
    assert(core.current()->identity.uid==99);assert(core.history()[0].app.identity.uid==10);
    // Keep ten newest PID transitions; no live process IDs manufactured by production code.
    for (int i=0;i<15;i++) {
        auto synthetic=empty();synthetic.rendering={client(50,500+i,"fixture","system_server")};
        core.evaluate(FocusType::Type0,{},synthetic,base(),now+std::chrono::seconds(i));
    }
    auto history=core.history();assert(history.size()==10);
    assert(history.front().app.identity.pid==514);assert(history.back().app.identity.pid==505);
    auto previous=core.current();bool rejected=false;
    try {core.evaluate(static_cast<FocusType>(2),{},empty(),base(),now);}
    catch(const std::invalid_argument&) {rejected=true;}
    assert(rejected);assert(core.current()->identity==previous->identity);
    // No shared references escape; querying snapshots concurrently with updates is safe.
    auto snapshot=core.history();snapshot.clear();assert(core.history().size()==10);
    const auto worker=[&]{for(int i=0;i<1000;i++) {
        core.evaluate(FocusType::Type0,queried,inputs,decision,now);
        assert(core.current().has_value());assert(core.history().size()<=10);
    }};
    std::thread one(worker),two(worker);worker();one.join();two.join();
}
