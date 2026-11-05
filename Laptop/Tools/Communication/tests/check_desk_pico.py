"""Test the actual desk Pico HTTP/JSON decoder, including fragmented responses.
Does not claim to test USB, radio or MCU timing.
"""
from pathlib import Path
import json
import subprocess

ROOT=Path(__file__).resolve().parents[4]
telemetry='STATUS BOARD=MSP430F5529 FW=SUPERVISOR_V2 LINK=READY RUN=0 CAL=NEEDED L2=NC R4=NC LED2=OFF FLAGS=96 RESULT=0 PENDING=0 UART_ERRORS=0 RX_DROPS=0 BAD_FRAMES=0 BRIDGE=ESP_UART_V1'
state={'board':'ESP32_FIREBEETLE','firmware':'DIRECT_WIFI_V1','main_controller':'MSP430F5529',
       'ap_ready':True,'msp_link':'UP','fresh':True,'age_ms':124,'telemetry':telemetry,
       'error':None,'pending_id':0,'stop_id':0,'stop_state':'NONE'}
valid=json.dumps(state,separators=(',',':'))
absent=dict(state,msp_link='NOT_CONNECTED',fresh=False,age_ms=None,telemetry=None)
stale=dict(state,msp_link='STALE',fresh=False,age_ms=4000)
bad=[]
for key in ('board','firmware','main_controller','ap_ready','msp_link','fresh','age_ms','telemetry'):
    copy=dict(state); del copy[key]; bad.append(json.dumps(copy,separators=(',',':')))
for key,value in [('board','PICO_W'),('firmware','BRIDGE2'),('main_controller','UNO'),
                  ('fresh','true'),('age_ms',4294967296),('age_ms',3500),('age_ms',None),
                  ('telemetry',None),('telemetry','STATUS BOARD=MSP430F5529 BRIDGE=I2C_V1'),
                  ('telemetry',telemetry+'\nFAKE'),('msp_link','DOWN')]:
    copy=dict(state); copy[key]=value; bad.append(json.dumps(copy,separators=(',',':')))
bad += [valid[:-1]+',"fresh":true}',valid+'garbage',valid.replace('"age_ms":124','"age_ms":0124'),
        valid[:-1]+',"nested":{"a":1}}',valid[:-1]+',"list":[1]}','{}','',valid[:100]]
cpp=r'''
#include <cassert>
#include <cstdio>
#include <string>
#include "bridge_response.h"
static unsigned checks;
#define CHECK(x) do { assert(x); ++checks; } while(0)
int main() {
    const char *valid=VALID_JSON;
    desk::State parsed;
    CHECK(desk::state(valid,parsed) && parsed.fresh && parsed.age==124 && parsed.hasTelemetry);
    CHECK(desk::state(ABSENT_JSON,parsed) && !parsed.fresh && !parsed.hasAge && !parsed.hasTelemetry);
    CHECK(desk::state(STALE_JSON,parsed) && !parsed.fresh && parsed.age==4000);
    for(const char *bad : {BAD_JSONS}) CHECK(!desk::state(bad,parsed));
    const std::string body=valid;
    const std::string raw="HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nContent-Length: "+std::to_string(body.size())+"\r\nConnection: close\r\n\r\n"+body;
    for(size_t split=0;split<=raw.size();++split) {
        desk::HttpResponse http;
        http.feed(raw.data(),split); http.feed(raw.data()+split,raw.size()-split);
        CHECK(http.complete() && !http.bad && desk::state(http.body(),parsed));
    }
    desk::HttpResponse bytewise;
    for(char c:raw) bytewise.feed(&c,1);
    CHECK(bytewise.complete() && desk::state(bytewise.body(),parsed));
    for(const char *header : {
        "HTTP/1.1 404 Nope\r\nContent-Length: 2\r\n\r\n{}",
        "HTTP/1.1 200 OK\r\nTransfer-Encoding: chunked\r\n\r\n2\r\n{}\r\n0\r\n\r\n",
        "HTTP/1.1 200 OK\r\nContent-Length: 2\r\nContent-Length: 2\r\n\r\n{}",
        "HTTP/1.1 200 OK\r\nContent-Length: 4294967296\r\n\r\n{}",
        "HTTP/1.1 200 OK\r\nContent-Length: 1601\r\n\r\n{}",
        "HTTP/1.1 200 OK\r\nContent-Length: 1\r\n\r\n{}",
        "HTTP/1.1 200 OK\r\nBroken\r\n\r\n{}",
        "HTTP/1.1 200 OK\r\n\r\n{}"}) {
        desk::HttpResponse http; http.feed(header,strlen(header)); CHECK(http.bad && !http.complete());
    }
    desk::HttpResponse incomplete;
    incomplete.feed(raw.data(),raw.size()-1); CHECK(!incomplete.bad && !incomplete.complete());
    desk::HttpResponse nul;
    std::string binary=raw; binary.push_back(0); nul.feed(binary.data(),binary.size()); CHECK(nul.bad);
    desk::HttpResponse huge;
    std::string longHeader(1100,'X'); huge.feed(longHeader.data(),longHeader.size()); CHECK(huge.bad);
    std::string upper=raw; upper.replace(upper.find("Content-Length"),14,"CONTENT-LENGTH");
    desk::HttpResponse casing; casing.feed(upper.data(),upper.size()); CHECK(casing.complete());
    printf("PASS %u desk bridge assertions: HTTP splits, lengths, JSON identity, stale data and malformed input.\n",checks);
}
'''
cpp=cpp.replace('VALID_JSON',json.dumps(valid)).replace('ABSENT_JSON',json.dumps(json.dumps(absent,separators=(',',':'))))
cpp=cpp.replace('STALE_JSON',json.dumps(json.dumps(stale,separators=(',',':'))))
cpp=cpp.replace('BAD_JSONS',','.join(json.dumps(s) for s in bad))
build=ROOT/'Laptop/Tools/Communication/build/desk-tests'; build.mkdir(parents=True,exist_ok=True)
source,exe=build/'desk_tests.cpp',build/'desk_tests.exe'
source.write_text(cpp,encoding='utf-8')
subprocess.run(['C:/msys64/ucrt64/bin/g++.exe','-std=c++17','-Wall','-Wextra','-Werror','-static',
               '-I'+str(ROOT/'Laptop/Pico_W/laptop_wifi_bridge'),'-I'+str(ROOT/'Car/ESP32_Gateway/robot_wifi_gateway'),
               str(source),'-o',str(exe)],check=True)
subprocess.run([str(exe)],check=True)
