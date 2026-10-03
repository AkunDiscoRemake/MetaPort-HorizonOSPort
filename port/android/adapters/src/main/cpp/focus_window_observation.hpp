// SPDX-License-Identifier: GPL-3.0-only
#pragma once
#include <cstdint>
#include <limits>
#include <stdexcept>

namespace metaport::focus {
// Externally serialized by the JNI registry mutex. Positive own-window evidence
// only: no observed window does NOT establish global (or whole-app) absence.
class WindowObservation final {
public:
    std::int64_t attach() {
        if (active_) throw std::logic_error("Window source already attached");
        if (source_==std::numeric_limits<std::int64_t>::max()) throw std::overflow_error("Window source exhausted");
        advance();++source_;active_=true;known_=false;return source_;
    }
    void observe(std::int64_t source,bool positive) {
        if (!active_ || source!=source_) throw std::logic_error("Foreign or closed window source");
        advance();known_=positive;
    }
    void detach(std::int64_t source) {
        if (!active_ || source!=source_) return; // An old owner cannot detach a replacement.
        active_=false;known_=false;
        if (generation_<std::numeric_limits<std::int64_t>::max()) ++generation_;
    }
    bool matches(std::int64_t source,std::int64_t generation) const {
        return active_ && known_ && source==source_ && generation>0 && generation==generation_;
    }
    std::int64_t source() const { return source_; }
    std::int64_t generation() const { return generation_; }
    bool known() const { return active_ && known_; }
private:
    void advance() {
        if (generation_==std::numeric_limits<std::int64_t>::max()) throw std::overflow_error("Window generation exhausted");
        ++generation_;
    }
    std::int64_t source_=0,generation_=0;
    bool active_=false,known_=false;
};
} // namespace metaport::focus
