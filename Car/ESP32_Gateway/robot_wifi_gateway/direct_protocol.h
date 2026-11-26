#pragma once
#include <stdint.h>
#include <stddef.h>
#include <string.h>

namespace direct {
enum class Op { None, Ping, Status, Stop, Target, Resume, Dock, Depart, Approach, RefillMinimum };
/* Return the UART operation name for op. */
inline const char *name(Op op) {
    switch(op) { case Op::Ping:return "PING"; case Op::Status:return "STATUS";
        case Op::Stop:return "STOP"; case Op::Target:return "TARGET";
        case Op::Resume:return "RESUME"; case Op::Dock:return "DOCK";
        case Op::Depart:return "DEPART"; case Op::Approach:return "APPROACH";
        case Op::RefillMinimum:return "RFMIN"; default:return ""; }
}
/* Check the NET reply prefix and parse its request id. On success payload points inside the
 * input line. */
inline bool frame(const char *line,uint32_t &id,const char *&payload) {
    if(strncmp(line,"NET ",4)) return false;
    const char *p=line+4; uint32_t n=0;
    if(*p<'1' || *p>'9') return false;
    while(*p>='0' && *p<='9') {
        const uint32_t d=static_cast<uint32_t>(*p++-'0');
        if(n>UINT32_MAX/10u || (n==UINT32_MAX/10u && d>UINT32_MAX%10u)) return false;
        n=n*10u+d;
    }
    if(*p++!=' ' || !*p) return false;
    id=n; payload=p; return true;
}
// Require one well-formed supervisor telemetry record, not arbitrary UART text.
/* Check that p is a supervisor status line carrying the expected firmware and transport
 * identity. */
inline bool status(const char *p) {
    constexpr const char *prefix="STATUS BOARD=MSP430F5529 FW=SUPERVISOR_V2 ";
    if(strncmp(p,prefix,strlen(prefix))) return false;
    const char *bridge=strstr(p," BRIDGE=ESP_UART_V1");
    if(!bridge || bridge[strlen(" BRIDGE=ESP_UART_V1")]) return false;
    return strstr(p," LINK=") && strstr(p," RUN=") && strstr(p," FLAGS=") &&
           strstr(p," UART_ERRORS=") && strstr(p," RX_DROPS=") && strstr(p," BAD_FRAMES=");
}
/* Check that response payload p belongs to the requested operation op. */
inline bool matches(Op op,const char *p) {
    if(op==Op::Ping) return !strcmp(p,"PONG MSP430 SUPERVISOR_V2 ESP_UART_V1");
    if(op==Op::Status) return status(p);
    if(op==Op::Target) return !strcmp(p,"TARGET ACCEPTED") || !strcmp(p,"TARGET REFUSED");
    if(op==Op::Resume) return !strcmp(p,"RESUME ACCEPTED") || !strcmp(p,"RESUME REFUSED");
    if(op==Op::Dock) return !strcmp(p,"DOCK ACCEPTED") || !strcmp(p,"DOCK REFUSED");
    if(op==Op::Depart) return !strcmp(p,"DEPART ACCEPTED") || !strcmp(p,"DEPART REFUSED");
    if(op==Op::Approach) return !strcmp(p,"APPROACH RECEIVED");
    if(op==Op::RefillMinimum) return !strcmp(p,"RFMIN ACCEPTED") || !strcmp(p,"RFMIN REFUSED");
    return op==Op::Stop && !strcmp(p,"STOP REQUESTED");
}
}
