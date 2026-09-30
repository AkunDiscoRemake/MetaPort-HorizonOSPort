#include "sample_cache.hpp"
#include <cassert>
#include <limits>
#include <thread>
using namespace metaport;
int main() {
    SampleCache cache;
    assert(!cache.read(100, 10)[0].observed);
    assert(!cache.put(SampleCache::Rotation, 1, {0,0,0,0}, 0));
    assert(!cache.put(SampleCache::Rotation, 1, {0,0,0,std::numeric_limits<float>::infinity()}, 0));
    assert(cache.put(SampleCache::Rotation, 100, {0,0,0,2}, 3));
    auto sample = cache.read(110, 10)[0];
    assert(sample.observed && sample.value[3] == 1 && sample.timestamp_ns == 100);
    assert(!cache.put(SampleCache::Rotation, 100, {1,0,0,0}, 3));
    assert(!cache.put(SampleCache::Rotation, 99, {1,0,0,0}, 3));
    assert(!cache.read(111, 10)[0].observed);
    assert(!cache.read(99, 100)[0].observed);
    assert(!cache.read(100, -1)[0].observed);
    assert(cache.put(SampleCache::Gyroscope, 101, {1,2,3,0}, 2));
    assert(!cache.read(101, 10)[2].observed); // Never infer acceleration/position.
    cache.reset();
    assert(!cache.read(102, 10)[1].observed);
    std::thread producer([&] {
        for (int64_t i=1; i<=10000; ++i) cache.put(SampleCache::Acceleration, i, {1,2,3,0}, 1);
    });
    for (int i=0; i<10000; ++i) (void)cache.read(10000, 10000);
    producer.join();
    assert(cache.read(10000, 0)[2].observed);
}
