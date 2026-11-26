#pragma once
#include <cstddef>
#include <cstdint>
#include <cstring>

namespace video {
// One completed newest-frame slot plus one in-progress frame. TCP can deliver a
// complete JPEG and part of the next one in the same poll; keep the completed
// bytes available until another whole frame replaces them. Never queue JPEGs.
struct Receiver {
    static constexpr size_t Max=32768;
    uint8_t header[16]{},buffers[2][Max]{};
    uint8_t *jpeg=buffers[0],*receiving=buffers[1];
    size_t headerUsed=0,bodyUsed=0,bodyLength=0,length=0;
    uint32_t bodyChecksum=0,bodySequence=0;
    uint32_t checksum=0,sequence=0,frames=0,dropped=0;
    bool ready=false,bad=false;
    /* Read one unsigned 32-bit field from the little-endian frame header at p. */
    static uint32_t le(const uint8_t *p) { return uint32_t(p[0])|(uint32_t(p[1])<<8)|(uint32_t(p[2])<<16)|(uint32_t(p[3])<<24); }
    /* Discard any partial camera header or JPEG and clear ready/error flags on reconnect. */
    void reset() { headerUsed=bodyUsed=bodyLength=length=0;ready=bad=false; }
    /* Accept size bytes at data across arbitrary TCP splits. Publish the completed JPEG by
     * exchanging buffers. */
    void feed(const uint8_t *data,size_t size) {
        while(size && !bad) {
            if(headerUsed<16) {
                const size_t n=size<16-headerUsed?size:16-headerUsed;
                memcpy(header+headerUsed,data,n);headerUsed+=n;data+=n;size-=n;
                if(headerUsed<16) continue;
                bodyLength=le(header+4);bodyChecksum=le(header+8);bodySequence=le(header+12);bodyUsed=0;
                if(memcmp(header,"PCV1",4) || bodyLength<4 || bodyLength>Max) { bad=true;break; }
            }
            const size_t n=size<bodyLength-bodyUsed?size:bodyLength-bodyUsed;
            memcpy(receiving+bodyUsed,data,n);bodyUsed+=n;data+=n;size-=n;
            if(bodyUsed==bodyLength) {
                if(ready) ++dropped;
                uint8_t *old=jpeg;jpeg=receiving;receiving=old;
                length=bodyLength;checksum=bodyChecksum;sequence=bodySequence;
                ready=true;++frames;headerUsed=0;
            }
        }
    }
};
}
