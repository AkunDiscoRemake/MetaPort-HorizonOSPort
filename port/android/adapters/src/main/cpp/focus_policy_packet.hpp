// SPDX-License-Identifier: GPL-3.0-only
#pragma once
#include "focus_immersive.hpp"
#include <cstring>

namespace metaport::focus::packet {
// Internal JNI transport, NOT the original Binder ABI. Decode completely before
// mutating policy state. Values must originate in a trusted observation producer.
constexpr std::size_t max_bytes=65536, max_rows=256, max_text=1024;
constexpr std::int32_t request_magic=0x3146504d, result_magic=0x3152504d;
inline void require(bool valid) { if (!valid) throw std::invalid_argument("Invalid focus policy packet"); }
inline bool utf8(const std::string& text) {
    std::size_t i=0;
    while (i<text.size()) {
        auto c=static_cast<unsigned char>(text[i++]);
        if (c<0x80) continue;
        unsigned remaining;std::uint32_t value,minimum;
        if (c>=0xc2 && c<=0xdf) { remaining=1;value=c&31;minimum=0x80; }
        else if (c>=0xe0 && c<=0xef) { remaining=2;value=c&15;minimum=0x800; }
        else if (c>=0xf0 && c<=0xf4) { remaining=3;value=c&7;minimum=0x10000; }
        else return false;
        if (text.size()-i<remaining) return false;
        while (remaining--) {
            auto next=static_cast<unsigned char>(text[i++]);
            if ((next&0xc0)!=0x80) return false;
            value=(value<<6)|(next&63);
        }
        if (value<minimum || value>0x10ffff || (value>=0xd800 && value<=0xdfff)) return false;
    }
    return true;
}
class Reader {
    const std::vector<std::uint8_t>& data_;std::size_t position_=0;
public:
    explicit Reader(const std::vector<std::uint8_t>& data):data_(data) { require(data.size()<=max_bytes); }
    std::int32_t integer() {
        require(data_.size()-position_>=4);
        std::uint32_t value=0;
        for (unsigned i=0;i<4;++i) value|=std::uint32_t(data_[position_++])<<(8*i);
        std::int32_t result;std::memcpy(&result,&value,4);return result;
    }
    std::int64_t timestamp() {
        std::uint64_t low=static_cast<std::uint32_t>(integer());
        std::uint64_t high=static_cast<std::uint32_t>(integer());
        const auto value=low|(high<<32);
        // system_clock uses nanoseconds in our Android/host targets; avoid overflow.
        require(value<=9223372036854ULL);return static_cast<std::int64_t>(value);
    }
    bool boolean() { auto value=integer();require(value==0 || value==1);return value==1; }
    std::size_t count() { auto value=integer();require(value>=0 && value<=static_cast<int>(max_rows));return value; }
    std::string text() {
        auto size=integer();require(size>=0 && size<=static_cast<int>(max_text));
        require(static_cast<std::size_t>(size)<=data_.size()-position_);
        std::string value(data_.begin()+position_,data_.begin()+position_+size);
        position_+=size;require(utf8(value));return value;
    }
    Client identity() { auto uid=integer();auto pid=integer();return {uid,pid}; }
    std::vector<Client> identities() {
        auto size=count();std::vector<Client> result;result.reserve(size);
        for (std::size_t i=0;i<size;++i) result.push_back(identity());
        return result;
    }
    ImmersiveClient metadata() {
        auto client=identity();auto package=text();auto process=text();auto top=text();
        return {client,std::move(package),std::move(process),std::move(top)};
    }
    std::vector<ImmersiveClient> metadata_list() {
        auto size=count();std::vector<ImmersiveClient> result;result.reserve(size);
        for (std::size_t i=0;i<size;++i) result.push_back(metadata());
        return result;
    }
    void finish() const { require(position_==data_.size()); }
};
struct Request {
    FocusType type;
    std::chrono::system_clock::time_point timestamp;
    std::vector<ClientMetadata> requested;
    DecisionInputs decisions;
    ImmersiveInputs immersive;
};
inline Request decode(const std::vector<std::uint8_t>& bytes) {
    Reader reader(bytes);require(reader.integer()==request_magic);
    auto type=reader.integer();require(type==0 || type==1);
    const auto timestamp=std::chrono::system_clock::time_point(std::chrono::milliseconds(reader.timestamp()));
    std::vector<ClientMetadata> requested;
    auto size=reader.count();requested.reserve(size);
    for (std::size_t i=0;i<size;++i) {
        auto identity=reader.identity();auto mask=reader.integer();require(mask>=0 && mask<=3);
        std::set<FocusType> access;
        if (mask&1) access.insert(FocusType::Type0);
        if (mask&2) access.insert(FocusType::Type1);
        requested.push_back({identity,std::move(access)});
    }
    auto activities=reader.identities();auto panels=reader.identities();
    auto top=reader.identities();auto all_top=reader.identities();
    std::optional<Client> window;
    if (reader.boolean()) window=reader.identity();
    const bool display=reader.boolean();
    auto rendering=reader.metadata_list();auto live=reader.metadata_list();
    std::vector<std::optional<ImmersiveClient>> foreground;
    size=reader.count();foreground.reserve(size);
    for (std::size_t i=0;i<size;++i) {
        if (reader.boolean()) foreground.push_back(reader.metadata());
        else foreground.push_back(std::nullopt);
    }
    auto primary=reader.text();reader.finish();
    return {static_cast<FocusType>(type),timestamp,std::move(requested),
        DecisionInputs{std::move(activities),std::move(panels),std::move(top),std::move(all_top),
                       window,std::nullopt,std::nullopt,display},
        ImmersiveInputs{std::move(rendering),std::move(live),std::move(foreground),std::move(primary)}};
}
class Writer {
public:
    std::vector<std::uint8_t> bytes;
    void integer(std::int32_t value) {
        require(bytes.size()<=max_bytes-4);
        auto bits=static_cast<std::uint32_t>(value);
        for (unsigned i=0;i<4;++i) bytes.push_back(static_cast<std::uint8_t>(bits>>(8*i)));
    }
    void timestamp(std::chrono::system_clock::time_point value) {
        auto time=std::chrono::duration_cast<std::chrono::milliseconds>(value.time_since_epoch()).count();
        const auto bits=static_cast<std::uint64_t>(time);
        for (unsigned i=0;i<2;++i) {
            auto word=static_cast<std::uint32_t>(bits>>(32*i));std::int32_t signed_word;
            std::memcpy(&signed_word,&word,4);integer(signed_word);
        }
    }
    void text(const std::string& value) {
        require(value.size()<=max_text && utf8(value));integer(static_cast<std::int32_t>(value.size()));
        require(value.size()<=max_bytes-bytes.size());bytes.insert(bytes.end(),value.begin(),value.end());
    }
    void identity(Client value) { integer(value.uid);integer(value.pid); }
    void app(const ImmersiveApp& value) { identity(value.identity);text(value.package_name);integer(value.is_top_activity); }
};
inline std::vector<std::uint8_t> encode(const PolicyEvaluation& result,int own_focus_mask,int evaluated_types,
                                      const std::vector<ImmersiveHistoryRecord>& history) {
    Writer writer;writer.bytes.reserve(max_bytes);writer.integer(result_magic);writer.text(result.top_activity);
    writer.integer(result.immersive.has_value());if (result.immersive) writer.app(*result.immersive);
    require(result.decisions.size()<=max_rows);writer.integer(static_cast<std::int32_t>(result.decisions.size()));
    for (const auto& row:result.decisions) {
        writer.identity(row.identity);writer.integer(static_cast<int>(row.type));writer.integer(row.has_focus);
    }
    writer.integer(own_focus_mask);writer.integer(evaluated_types);require(history.size()<=10);writer.integer(static_cast<std::int32_t>(history.size()));
    for (const auto& row:history) { writer.timestamp(row.timestamp);writer.app(row.app); }
    return std::move(writer.bytes);
}
} // namespace metaport::focus::packet
