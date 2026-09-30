#pragma once
#include <array>
#include <cmath>
#include <cstdint>
#include <mutex>

namespace metaport {
// Internal semantic actions only. These values are NOT a Quest/OpenXR/private ABI.
enum Button : uint32_t { A=1, B=2, X=4, Y=8, Menu=16, Stick=32, Trigger=64, Grip=128 };
enum class InputMode : int { HandsRequested=0, JoyCons=1 };
struct ControllerState {
    int device_id=-1;
    uint32_t buttons=0, pressed=0, released=0;
    float stick_x=0, stick_y=0;
    bool stick_valid=false;
    // Public Android gamepad events supply neither calibrated orientation nor position.
    bool orientation_valid=false, position_valid=false;
    int64_t event_time_ns=0;
    int64_t key_time_ns=0, axis_time_ns=0;
};
struct InputSnapshot {
    InputMode mode=InputMode::HandsRequested;
    std::array<ControllerState,2> controllers{};
    // No original hand provider is connected yet; never publish a fake skeleton.
    bool original_hand_provider_connected=false;
};
class InputRouter {
    std::mutex mutex_;
    std::array<ControllerState,2> states_{};
public:
    bool connect(int id, int side) {
        if (id<0 || side<0 || side>1) return false;
        std::lock_guard<std::mutex> lock(mutex_);
        for (int i=0;i<2;++i) if (i!=side && states_[i].device_id==id) return false;
        auto &s=states_[side];
        if (s.device_id==id) return true;
        if (s.device_id!=-1) return false; // Do not silently replace one person's controller.
        const auto released=s.released;
        s=ControllerState{};s.device_id=id;s.released=released;return true;
    }
    void disconnect(int id) {
        std::lock_guard<std::mutex> lock(mutex_);
        for (auto &s:states_) if (s.device_id==id) {
            const auto released=s.buttons|s.released;
            s=ControllerState{};s.released=released;
        }
    }
    void reset() {
        std::lock_guard<std::mutex> lock(mutex_);
        for (auto &s:states_) {
            const auto released=s.buttons|s.released;
            s=ControllerState{};s.released=released;
        }
    }
    bool key(int id, uint32_t button, bool down, int64_t time_ns) {
        if (id<0 || !button || (button & (button-1)) || button>Grip || time_ns<=0) return false;
        std::lock_guard<std::mutex> lock(mutex_);
        for (auto &s:states_) if (s.device_id==id) {
            if (time_ns<s.key_time_ns) return false;
            s.key_time_ns=time_ns;
            if (time_ns>s.event_time_ns) s.event_time_ns=time_ns;
            if (down) { s.pressed|=button & ~s.buttons;s.buttons|=button; }
            else { s.released|=button & s.buttons;s.buttons&=~button; }
            return true;
        }
        return false;
    }
    bool axis(int id, float x, float y, int64_t time_ns) {
        if (id<0 || !std::isfinite(x) || !std::isfinite(y) ||
            x < -1 || x > 1 || y < -1 || y > 1 || time_ns<=0) return false;
        std::lock_guard<std::mutex> lock(mutex_);
        for (auto &s:states_) if (s.device_id==id) {
            if (time_ns<s.axis_time_ns) return false;
            s.axis_time_ns=time_ns;
            if (time_ns>s.event_time_ns) s.event_time_ns=time_ns;
            s.stick_x=x;s.stick_y=y;s.stick_valid=true;return true;
        }
        return false;
    }
    InputSnapshot snapshot() { return read(false); }
    // Single frame consumer: preserve short taps; repeated edges coalesce per action.
    InputSnapshot drain() { return read(true); }
private:
    InputSnapshot read(bool clear_edges) {
        std::lock_guard<std::mutex> lock(mutex_);
        InputSnapshot out;out.controllers=states_;
        for (const auto &s:states_) if (s.device_id>=0) out.mode=InputMode::JoyCons;
        if (clear_edges) for (auto &s:states_) { s.pressed=0;s.released=0; }
        return out;
    }
};
} // namespace metaport
