#include "input_router.hpp"
#include <cassert>
#include <limits>
#include <thread>
using namespace metaport;
int main() {
    InputRouter r;
    assert(r.snapshot().mode==InputMode::HandsRequested);
    assert(!r.snapshot().original_hand_provider_connected);
    assert(!r.key(-1,A,true,1));assert(!r.axis(-1,0,0,1));
    assert(!r.connect(-1,0));assert(!r.connect(3,2));
    assert(r.connect(3,0));assert(r.connect(3,0));
    assert(!r.connect(3,1));assert(!r.connect(4,0));
    assert(r.snapshot().mode==InputMode::JoyCons);
    assert(!r.snapshot().controllers[1].orientation_valid);
    assert(r.key(3,X,true,100));assert(r.key(3,Trigger,true,100));
    assert(!r.key(3,A|B,true,100));assert(!r.key(3,256,true,100));
    assert(!r.key(3,X,false,99));
    assert(r.axis(3,0.25f,-1,110));
    // Key and axis channels have separate timestamp ordering.
    assert(r.key(3,X,false,105));
    assert(r.snapshot().controllers[0].buttons==Trigger);
    assert(!r.axis(3,2,0,120));
    assert(!r.axis(3,std::numeric_limits<float>::quiet_NaN(),0,120));
    assert(!r.axis(3,0,0,109));
    assert(r.connect(4,1));assert(r.key(4,A,true,120));
    r.disconnect(3);
    auto state=r.snapshot();
    assert(state.mode==InputMode::JoyCons);
    assert(state.controllers[0].buttons==0 && !state.controllers[0].stick_valid);
    assert(state.controllers[1].buttons==A && !state.controllers[1].position_valid);
    r.disconnect(4);assert(r.snapshot().mode==InputMode::HandsRequested);
    assert(r.connect(3,0));assert(r.snapshot().controllers[0].buttons==0);
    r.drain();
    assert(r.key(3,X,true,1));assert(r.key(3,X,false,2));
    auto tap=r.drain();
    assert(tap.controllers[0].buttons==0);
    assert(tap.controllers[0].pressed==X && tap.controllers[0].released==X);
    assert(r.drain().controllers[0].pressed==0);
    assert(r.key(3,Grip,true,3));r.disconnect(3);assert(r.connect(3,0));
    assert(r.drain().controllers[0].released==Grip);
    std::thread producer([&]{for(int i=1;i<10000;++i) r.key(3,X,(i%2)!=0,i);});
    for(int i=0;i<10000;++i) assert(!r.snapshot().controllers[0].position_valid);
    producer.join();
    r.reset();assert(r.snapshot().controllers[0].device_id==-1);
    assert(!r.snapshot().original_hand_provider_connected);
}
