"""Exercise the actual direct-UART command gate and ESP reply parser on host.
Does not claim to test electrical wiring, radio or MCU peripheral timing.
"""
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[4]
source = (ROOT / 'Car/MSP430/robot_supervisor/main.c').read_text()

def function(name, return_type='void'):
    start = source.index('static ' + return_type + ' ' + name + '(')
    brace = source.index('{', start)
    depth, end = 1, brace + 1
    while depth:
        depth += (source[end] == '{') - (source[end] == '}')
        end += 1
    return source[start:end] + '\n'

prefix = r'''
#define SUPERVISOR_ESP_UART
#include <cassert>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <string>
#include "direct_protocol.h"
static uint8_t running=1,P4OUT=128,queued=0;
static const uint8_t BIT7=128,RL_STOP=2;
static char usbLine[32]; static uint8_t usbUsed;
static std::string output;
static void print(const char *s) { output+=s; }
static uint8_t put(uint8_t,uint8_t c) { output+=static_cast<char>(c); return 1; }
static void status() {
    print("STATUS BOARD=MSP430F5529 FW=SUPERVISOR_V2 LINK=READY RUN=0 CAL=NEEDED L2=NC R4=NC LED2=OFF FLAGS=96 RESULT=0 PENDING=0 UART_ERRORS=0 RX_DROPS=0 BAD_FRAMES=0 BRIDGE=ESP_UART_V1\r\n");
}
static unsigned checks;
#define CHECK(x) do { assert(x); ++checks; } while(0)
'''
tests = r'''
static void user(const char *line) {
    assert(strlen(line)<sizeof(usbLine)); strcpy(usbLine,line); usbUsed=strlen(line);
    output.clear(); command();
}
static const char *payload(uint32_t expected) {
    static std::string stripped; stripped=output;
    if(stripped.size()>=2) stripped.resize(stripped.size()-2);
    uint32_t id=0; const char *p=nullptr;
    CHECK(direct::frame(stripped.c_str(),id,p) && id==expected);
    return p;
}
int main() {
    user("NET 1 PING"); CHECK(direct::matches(direct::Op::Ping,payload(1)));
    user("NET 4294967295 STATUS"); CHECK(direct::matches(direct::Op::Status,payload(UINT32_MAX)));
    CHECK(running && queued==0);
    user("NET 99 STOP"); CHECK(direct::matches(direct::Op::Stop,payload(99)));
    CHECK(!running && queued==RL_STOP && P4OUT==0);
    for(const char *bad : {"NET 0 STOP","NET 01 STOP","NET -1 STOP","NET 4294967296 STOP",
            "NET 99999999999 STOP","NET 2X STOP","NET 2","NET 2  STOP",
            "NET 2 START","NET 2 F","NET 2 W","NET 2 B","NET 2 C","NET 2 SPRAY",
            "F","START","W","B","C","NET 3 STOP EXTRA"}) {
        queued=0; running=1; P4OUT=128;
        user(bad); CHECK(queued==0 && running && P4OUT==128);
        CHECK(output.find("STOP REQUESTED")==std::string::npos);
    }
    uint32_t id=0; const char *p=nullptr;
    for(const char *bad : {"NET 0 PONG","NET 01 PONG","NET 4294967296 PONG",
            "NET 2X STATUS","NET 2 ","STATUS BOARD=MSP430F5529"})
        CHECK(!direct::frame(bad,id,p));
    CHECK(!direct::matches(direct::Op::Ping,"PONG PICO_W"));
    CHECK(!direct::matches(direct::Op::Stop,"STOP CONFIRMED"));
    CHECK(!direct::matches(direct::Op::Status,"STATUS BOARD=MSP430F5529 FW=SUPERVISOR_V2 BRIDGE=I2C_V1"));
    CHECK(!direct::matches(direct::Op::Status,"STATUS BOARD=MSP430F5529 FW=SUPERVISOR_V2 BRIDGE=ESP_UART_V1"));
    printf("PASS %u direct-bridge assertions: ID boundaries, actual MSP gate, STOP only, identity and reply matching.\n",checks);
}
'''
build = ROOT / 'Laptop/Tools/Communication/build/direct-tests'
build.mkdir(parents=True, exist_ok=True)
cpp, exe = build / 'direct_tests.cpp', build / 'direct_tests.exe'
cpp.write_text(prefix + function('stopRequested') + function('netCommand', 'uint8_t') + function('command') + tests)
subprocess.run(['C:/msys64/ucrt64/bin/g++.exe', '-std=c++17', '-Wall', '-Wextra', '-Werror', '-static',
                '-I' + str(ROOT / 'Car/ESP32_Gateway/robot_wifi_gateway'), str(cpp), '-o', str(exe)], check=True)
subprocess.run([str(exe)], check=True)
