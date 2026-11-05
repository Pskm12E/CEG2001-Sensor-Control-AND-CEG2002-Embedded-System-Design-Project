"""Compile and execute the Pico's real bounded Wi-Fi video frame decoder."""
from pathlib import Path
import subprocess

ROOT=Path(__file__).resolve().parents[4]
build=ROOT/'Laptop/Tools/Communication/build/video-tests';build.mkdir(parents=True,exist_ok=True)
source=build/'video_test.cpp';exe=build/'video_test.exe'
source.write_text(r'''
#include <cassert>
#include <cstdio>
#include <string>
#include "video_receiver.h"
static void put(std::string &s,unsigned offset,uint32_t v) { for(unsigned n=0;n<4;++n) s[offset+n]=char(v>>(8*n)); }
static std::string frame(size_t n) {
    std::string raw(16+n,'X');raw.replace(0,4,"PCV1");put(raw,4,n);put(raw,8,0x12345678);put(raw,12,50);return raw;
}
int main() {
    unsigned checks=0;const auto raw=frame(4000);
    for(size_t split=0;split<=raw.size();++split) {
        video::Receiver r;r.feed((const uint8_t*)raw.data(),split);r.feed((const uint8_t*)raw.data()+split,raw.size()-split);
        assert(!r.bad && r.ready && r.length==4000 && r.sequence==50 && r.checksum==0x12345678);++checks;
    }
    video::Receiver r;auto huge=frame(32769);r.feed((const uint8_t*)huge.data(),16);assert(r.bad);++checks;
    r.reset();auto maximum=frame(32768);r.feed((const uint8_t*)maximum.data(),maximum.size());assert(r.ready && !r.bad);++checks;
    r.reset();auto two=raw+raw;r.feed((const uint8_t*)two.data(),two.size());assert(r.ready && r.frames==3 && r.dropped==1);++checks;
    r.reset();auto bad=raw;bad[0]='?';r.feed((const uint8_t*)bad.data(),bad.size());assert(r.bad);++checks;
    printf("PASS %u camera decoder assertions: TCP fragmentation, bounds and latest-frame replacement.\n",checks);
}
''',encoding='utf-8')
subprocess.run(['C:/msys64/ucrt64/bin/g++.exe','-std=c++17','-Wall','-Wextra','-Werror','-static',
                '-I'+str(ROOT/'Laptop/Pico_W/laptop_wifi_bridge'),str(source),'-o',str(exe)],check=True)
subprocess.run([str(exe)],check=True)
