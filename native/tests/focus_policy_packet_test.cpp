// SPDX-License-Identifier: GPL-3.0-only
#include "focus_policy_packet.hpp"
#include <cassert>
#include <random>
using namespace metaport::focus;
static std::vector<std::uint8_t> fixture() {
    packet::Writer w;w.integer(packet::request_magic);w.integer(0);w.timestamp({});
    w.integer(1);w.identity({10,100});w.integer(0);
    w.integer(1);w.identity({10,100});
    for(int i=0;i<3;++i) w.integer(0);
    w.integer(0);w.integer(1); // absent window, observed main-display focus
    for(int i=0;i<3;++i) w.integer(0);
    w.text("");return w.bytes;
}
static void invalid(const std::vector<std::uint8_t>& bytes) {
    bool rejected=false;try { (void)packet::decode(bytes); }
    catch (const std::invalid_argument&) { rejected=true; }
    assert(rejected);
}
int main() {
    auto bytes=fixture();auto decoded=packet::decode(bytes);
    assert(decoded.requested.size()==1);
    assert(decoded.decisions.foreground_activities.size()==1);
    assert(decoded.decisions.main_display_focus);
    assert(!decoded.decisions.window_focus);
    FocusPolicyCore core;core.install_client_record({10,100});
    auto result=core.evaluate(decoded.type,decoded.requested,decoded.immersive,decoded.decisions,decoded.timestamp);
    assert(result.decisions.size()==1 && result.decisions[0].has_focus);
    auto encoded=packet::encode(result,1,core.history());
    packet::Reader reader(encoded);assert(reader.integer()==packet::result_magic);
    assert(reader.text().empty());assert(!reader.boolean());assert(reader.count()==1);
    assert((reader.identity()==Client{10,100}));assert(reader.integer()==0);assert(reader.boolean());
    assert(reader.integer()==1);assert(reader.count()==0);reader.finish();
    for(std::size_t i=0;i<bytes.size();++i) invalid({bytes.begin(),bytes.begin()+i});
    auto changed=bytes;changed.push_back(0);invalid(changed);
    for(std::size_t offset:{0U,4U,16U,28U}) {
        changed=bytes;changed[offset]=255;invalid(changed);
    }
    changed=bytes;changed[15]=128;invalid(changed); // negative timestamp
    invalid(std::vector<std::uint8_t>(packet::max_bytes+1));
    for(const auto& text:{std::string("\xc0\x80"),std::string("\xed\xa0\x80"),
                         std::string("\xf4\x90\x80\x80"),std::string("\xe2\x82"),std::string("\x80")}) {
        assert(!packet::utf8(text));
        changed=bytes;changed.resize(changed.size()-4);
        packet::Writer tail;tail.integer(static_cast<int>(text.size()));
        changed.insert(changed.end(),tail.bytes.begin(),tail.bytes.end());
        changed.insert(changed.end(),text.begin(),text.end());invalid(changed);
    }
    assert(packet::utf8(std::string("\0\xf0\x9f\x98\x80",5)));
    packet::Writer signed_values;signed_values.integer(INT32_MIN);signed_values.integer(INT32_MAX);
    packet::Reader signed_reader(signed_values.bytes);
    assert(signed_reader.integer()==INT32_MIN);assert(signed_reader.integer()==INT32_MAX);
    // Bounded deterministic malformed-input exercise under ASan/UBSan.
    std::mt19937 random(7421);
    for(int i=0;i<10000;++i) {
        changed=bytes;changed[random()%changed.size()]=static_cast<std::uint8_t>(random());
        try { auto value=packet::decode(changed);assert(value.requested.size()<=packet::max_rows); }
        catch (const std::invalid_argument&) {}
    }
}
