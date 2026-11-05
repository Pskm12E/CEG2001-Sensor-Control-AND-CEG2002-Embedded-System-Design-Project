#pragma once
#include <cstddef>
#include <cstdint>
#include <cstring>

namespace video {
// One bounded newest-frame slot; never allocate a queue of JPEGs.
struct Receiver {
    static constexpr size_t Max=32768;
    uint8_t header[16]{},jpeg[Max]{};
    size_t headerUsed=0,bodyUsed=0,length=0;
    uint32_t checksum=0,sequence=0,frames=0,dropped=0;
    bool ready=false,bad=false;
    static uint32_t le(const uint8_t *p) { return uint32_t(p[0])|(uint32_t(p[1])<<8)|(uint32_t(p[2])<<16)|(uint32_t(p[3])<<24); }
    void reset() { headerUsed=bodyUsed=length=0;ready=bad=false; }
    void feed(const uint8_t *data,size_t size) {
        while(size && !bad) {
            if(headerUsed<16) {
                if(!headerUsed && ready) { ready=false;++dropped; }
                const size_t n=size<16-headerUsed?size:16-headerUsed;
                memcpy(header+headerUsed,data,n);headerUsed+=n;data+=n;size-=n;
                if(headerUsed<16) continue;
                length=le(header+4);checksum=le(header+8);sequence=le(header+12);bodyUsed=0;
                if(memcmp(header,"PCV1",4) || length<4 || length>Max) { bad=true;break; }
            }
            const size_t n=size<length-bodyUsed?size:length-bodyUsed;
            memcpy(jpeg+bodyUsed,data,n);bodyUsed+=n;data+=n;size-=n;
            if(bodyUsed==length) { ready=true;++frames;headerUsed=0; }
        }
    }
};
}
