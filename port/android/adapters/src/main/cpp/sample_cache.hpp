#pragma once
#include <array>
#include <cmath>
#include <cstdint>
#include <mutex>

namespace metaport {
// MetaPort hardware contract, NOT an inferred Horizon ABI.
struct VectorSample {
    int64_t timestamp_ns = 0;  // Android sensor CLOCK_BOOTTIME timebase.
    std::array<float, 4> value{};
    int accuracy = -1;  // Raw Android accuracy, not tracking confidence.
    bool observed = false;
};

inline bool normalize_quaternion(std::array<float, 4>& q) {
    double norm2 = 0;
    for (float x : q) {
        if (!std::isfinite(x)) return false;
        norm2 += static_cast<double>(x) * x;
    }
    if (norm2 < 1e-12) return false;
    const double inv = 1.0 / std::sqrt(norm2);
    for (float& x : q) x = static_cast<float>(x * inv);
    return true;
}

class SampleCache {
public:
    enum Kind { Rotation = 0, Gyroscope = 1, Acceleration = 2 };
    void reset() {
        std::lock_guard<std::mutex> lock(mutex_);
        samples_ = {};
    }
    bool put(Kind kind, int64_t timestamp, std::array<float, 4> value, int accuracy) {
        if (kind < Rotation || kind > Acceleration || timestamp <= 0) return false;
        if (kind == Rotation && !normalize_quaternion(value)) return false;
        for (float x : value) if (!std::isfinite(x)) return false;
        std::lock_guard<std::mutex> lock(mutex_);
        auto& sample = samples_[kind];
        if (timestamp <= sample.timestamp_ns) return false;
        sample = {timestamp, value, accuracy, true};
        return true;
    }
    std::array<VectorSample, 3> read(int64_t now, int64_t max_age) const {
        std::lock_guard<std::mutex> lock(mutex_);
        auto result = samples_;
        for (auto& sample : result) {
            if (max_age < 0 || now < sample.timestamp_ns ||
                now - sample.timestamp_ns > max_age || !sample.observed) {
                sample = {};  // No stale/identity pose advertised as tracking.
            }
        }
        return result;
    }
private:
    mutable std::mutex mutex_;
    std::array<VectorSample, 3> samples_{};
};
}
