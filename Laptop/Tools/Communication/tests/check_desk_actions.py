"""Run actual Pico command/HTTP action functions against fake TCP, never USB/Wi-Fi."""
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[4]
subprocess.run(["g++", "-std=c++17", "-fsyntax-only",
                "-I" + str(ROOT / "Laptop/Tools/Communication/libraries/RobotBench/src"),
                str(Path(__file__).with_name("protocol_tests.cpp"))], check=True)
source = (ROOT / "Laptop/Pico_W/laptop_wifi_bridge/main.cpp").read_text()


def function(name, returns="void"):
    prefix = "static " + returns + ("" if returns.endswith("*") else " ") + name + "("
    start = source.index(prefix)
    brace = source.index("{", start)
    depth, end = 1, brace+1
    while depth:
        depth += (source[end] == "{") - (source[end] == "}")
        end += 1
    return source[start:end] + "\n"


prefix = r'''
#include <cassert>
#include <cstdio>
#include <cstdarg>
#include <string>
#include "bridge_response.h"
struct tcp_pcb {};
struct ip_addr_t {};
using err_t=int;
enum { ERR_OK=0, TCP_WRITE_FLAG_COPY=1, IPADDR_TYPE_V4=0 };
static tcp_pcb pcb;
static tcp_pcb *connection=nullptr;
static unsigned aborted,closed;
static std::string sent,output;
static int capturedPrintf(const char *format,...) {
    char text[4096]; va_list args; va_start(args,format);
    const int n=vsnprintf(text,sizeof(text),format,args); va_end(args); output+=text; return n;
}
#define printf capturedPrintf
static void tcp_arg(tcp_pcb*,void*) {}
template<class T> static void tcp_recv(tcp_pcb*,T) {}
template<class T> static void tcp_err(tcp_pcb*,T) {}
static err_t tcp_close(tcp_pcb*) { ++closed; return ERR_OK; }
static void tcp_abort(tcp_pcb*) { ++aborted; }
static tcp_pcb *tcp_new_ip_type(int) { return &pcb; }
static void ipaddr_aton(const char*,ip_addr_t*) {}
template<class T> static err_t tcp_connect(tcp_pcb*,ip_addr_t*,int,T) { return ERR_OK; }
static err_t tcp_write(tcp_pcb*,const char *p,size_t n,int) { sent.assign(p,n); return ERR_OK; }
static err_t tcp_output(tcp_pcb*) { return ERR_OK; }
static void received() {}
static void networkError() {}
static uint32_t clockNow;
static bool wifi=true;
static uint32_t nowMs() { return clockNow; }
static bool wifiUp() { return wifi; }
static bool espUp(uint32_t) { return true; }
static bool mspUp(uint32_t) { return true; }
enum class Reply { None,Ping,State,Msp,Stop,Target,Resume,Dock,Depart,Approach,RefillMinimum };
static Reply wanted=Reply::None;
static uint32_t resumeToken;
static desk::HttpResponse response;
static desk::State remote;
static bool done,failed,haveState,attempted;
static uint32_t started,lastAttempt,lastGood;
static int tcpError,lastTcpError;
static unsigned goodReads,failedReads;
static const char *fault="NONE",*lastFault="NONE";
static char lastFailure[3072];
static size_t failedBytes,failedBody,failedLength;
static bool videoWanted,videoConnected;
static uint32_t videoAttempt;
static struct { unsigned frames=0,dropped=0; } videoFrames;
static void closeVideo() {}
'''
tests = r'''
#undef printf
static unsigned checks;
#define CHECK(x) do { assert(x); ++checks; } while(0)
static void accepted(uint32_t id) {
    std::string body="{\"request_id\":"+std::to_string(id)+",\"state\":\"SENT_OUTCOME_UNKNOWN\"}";
    const std::string raw="HTTP/1.1 202 Accepted\r\nContent-Length: "+std::to_string(body.size())+"\r\n\r\n"+body;
    response.feed(raw.data(),raw.size()); done=true; finishRequest();
}
int main() {
    CHECK(beginRequest(Reply::None));
    connected(nullptr,connection,ERR_OK); CHECK(sent.find("GET /api/state ")==0);
    CHECK(beginRequest(Reply::Target) && closed==1 && wanted==Reply::Target);
    connected(nullptr,connection,ERR_OK); CHECK(sent.find("POST /api/target ")==0);
    CHECK(!beginRequest(Reply::Target));
    CHECK(beginRequest(Reply::Stop) && aborted==1 && wanted==Reply::Stop);
    connected(nullptr,connection,ERR_OK); CHECK(sent.find("POST /api/stop ")==0);
    CHECK(!beginRequest(Reply::Resume,42));
    accepted(17); CHECK(output.find("ROBOT STOP SENT ID=17")!=std::string::npos);
    CHECK(!connection && wanted==Reply::None);
    CHECK(beginRequest(Reply::Resume,42));
    CHECK(!beginRequest(Reply::Resume,99) && resumeToken==42);
    connected(nullptr,connection,ERR_OK); CHECK(sent.find("POST /api/resume?job_id=42 ")==0);
    accepted(18); CHECK(output.find("ROBOT RESUME SENT ID=18")!=std::string::npos);
    command("ROBOT APPROACH"); CHECK(wanted==Reply::Approach);
    connected(nullptr,connection,ERR_OK); CHECK(sent.find("POST /api/approach ")==0);
    command("ROBOT DOCK 4294967295"); CHECK(wanted==Reply::Dock);
    connected(nullptr,connection,ERR_OK); CHECK(sent.find("POST /api/dock?job_id=4294967295 ")==0);
    accepted(19);
    command("ROBOT DEPART 4294967295"); CHECK(wanted==Reply::Depart);
    connected(nullptr,connection,ERR_OK); CHECK(sent.find("POST /api/depart?job_id=4294967295 ")==0);
    accepted(20);
    command("ROBOT DEPART 4294967296"); CHECK(!connection && wanted==Reply::None);
    command("ROBOT RFMIN 2104"); CHECK(wanted==Reply::RefillMinimum);
    connected(nullptr,connection,ERR_OK); CHECK(sent.find("POST /api/refill-minimum?raw=2104 ")!=std::string::npos);
    accepted(21);
    command("ROBOT RFMIN 0"); CHECK(!connection && wanted==Reply::None);
    command("ROBOT RFMIN 4097"); CHECK(!connection && wanted==Reply::None);
    command("ROBOT TARGET"); CHECK(wanted==Reply::Target);
    failed=done=true; output.clear(); finishRequest();
    CHECK(output=="ROBOT TARGET ERROR NOT_CONFIRMED_NO_REPLAY\n");
    CHECK(!connection && wanted==Reply::None);
    CHECK(beginRequest(Reply::None));
    connected(nullptr,connection,ERR_OK); CHECK(sent.find("GET /api/state ")==0);
    closeConnection(); wanted=Reply::None;
    for(const char *bad:{"ROBOT START","ROBOT SPRAY","ROBOT CALIBRATE","ROBOT RESUME 0",
                        "ROBOT RESUME 01","ROBOT RESUME 4294967296","ROBOT RESUME 2 EXTRA"}) {
        command(bad); CHECK(!connection && wanted==Reply::None);
    }
    command("ROBOT RESUME 4294967295"); CHECK(wanted==Reply::Resume && resumeToken==UINT32_MAX);
    closeConnection(); wanted=Reply::None; wifi=false; output.clear();
    command("ROBOT TARGET"); CHECK(output=="ROBOT TARGET ERROR WIFI_DOWN_OR_BUSY\n" && !connection);
    std::printf("PASS %u actual Pico command, preemption, HTTP dispatch, ID, cancellation and no-replay assertions.\n",checks);
}
'''
build = ROOT / "Laptop/Tools/Communication/build/desk-action-tests"
build.mkdir(parents=True, exist_ok=True)
cpp, exe = build / "actions.cpp", build / "actions.exe"
parts = [("action", "bool"), ("actionName", "const char *"), ("closeConnection", "void"),
         ("errorReply", "void"), ("connected", "err_t"), ("beginRequest", "bool"),
         ("finishRequest", "void"), ("command", "void")]
cpp.write_text(prefix + "".join(function(*p) for p in parts) + tests, encoding="utf-8")
subprocess.run(["g++", "-std=c++17", "-Wall", "-Wextra", "-Werror",
                "-Wno-unused-variable", "-static", "-I" + str(ROOT / "Laptop/Pico_W/laptop_wifi_bridge"),
                "-I" + str(ROOT / "Car/ESP32_Gateway/robot_wifi_gateway"), str(cpp), "-o", str(exe)], check=True)
subprocess.run([str(exe)], check=True)
