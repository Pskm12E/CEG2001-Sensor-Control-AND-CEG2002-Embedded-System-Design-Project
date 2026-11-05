#pragma once
#include <stdint.h>
#include <stddef.h>
#include <string.h>
#include "direct_protocol.h"

namespace desk {
struct State {
    char board[32]{},firmware[32]{},main[32]{},link[24]{},telemetry[320]{};
    bool fresh=false,ap=false,hasAge=false,hasTelemetry=false;
    uint32_t age=0;
};
inline bool number(const char *p,uint32_t &n) {
    n=0; if(!*p || (*p=='0' && p[1])) return false;
    for(;*p;++p) {
        if(*p<'0' || *p>'9') return false;
        const uint32_t d=static_cast<uint32_t>(*p-'0');
        if(n>UINT32_MAX/10u || (n==UINT32_MAX/10u && d>UINT32_MAX%10u)) return false;
        n=n*10u+d;
    }
    return true;
}
inline void space(const char *&p) { while(*p==' ' || *p=='\r' || *p=='\n' || *p=='\t') ++p; }
inline bool string(const char *&p,char *out,size_t cap) {
    if(*p++!='"') return false;
    size_t n=0;
    while(*p && *p!='"') {
        unsigned char c=*p++;
        if(c=='\\') { c=*p++; if(c!='"' && c!='\\') return false; }
        if(c<32 || c>126 || n+1>=cap) return false;
        out[n++]=static_cast<char>(c);
    }
    if(*p!='"') return false;
    ++p; out[n]=0; return true;
}
template<size_t N> inline bool copy(char (&out)[N],const char *in) {
    if(strlen(in)>=N) return false;
    strcpy(out,in); return true;
}
// The ESP API is a bounded, flat JSON object. Duplicate known keys and nested
// values are rejected; quoted strings never become terminal control bytes.
inline bool state(const char *p,State &result) {
    State s; unsigned keys=0;
    space(p); if(*p++!='{') return false;
    for(;;) {
        char key[32],value[384]; space(p);
        if(!string(p,key,sizeof(key))) return false;
        space(p); if(*p++!=':') return false; space(p);
        const bool quoted=*p=='"';
        if(quoted) { if(!string(p,value,sizeof(value))) return false; }
        else {
            size_t n=0;
            while(*p && *p!=',' && *p!='}' && *p!=' ' && *p!='\r' && *p!='\n' && *p!='\t') {
                if(*p=='{' || *p=='[' || n+1>=sizeof(value)) return false;
                value[n++]=*p++;
            }
            value[n]=0; if(!n) return false;
        }
        unsigned bit=0; bool ok=true;
        if(!strcmp(key,"board")) { bit=1; ok=quoted && copy(s.board,value); }
        else if(!strcmp(key,"firmware")) { bit=2; ok=quoted && copy(s.firmware,value); }
        else if(!strcmp(key,"main_controller")) { bit=4; ok=quoted && copy(s.main,value); }
        else if(!strcmp(key,"msp_link")) { bit=8; ok=quoted && copy(s.link,value); }
        else if(!strcmp(key,"fresh")) { bit=16; ok=!quoted && (!strcmp(value,"true") || !strcmp(value,"false")); s.fresh=!strcmp(value,"true"); }
        else if(!strcmp(key,"ap_ready")) { bit=32; ok=!quoted && (!strcmp(value,"true") || !strcmp(value,"false")); s.ap=!strcmp(value,"true"); }
        else if(!strcmp(key,"age_ms")) { bit=64; s.hasAge=strcmp(value,"null")!=0; ok=!quoted && (!s.hasAge || number(value,s.age)); }
        else if(!strcmp(key,"telemetry")) { bit=128; s.hasTelemetry=quoted; ok=quoted?copy(s.telemetry,value):!strcmp(value,"null"); }
        if(!ok || (bit && (keys&bit))) return false;
        keys|=bit; space(p);
        if(*p=='}') { ++p; break; }
        if(*p++!=',') return false;
    }
    space(p);
    if(*p || keys!=255 || strcmp(s.board,"ESP32_FIREBEETLE") || strcmp(s.firmware,"DIRECT_WIFI_V1") || strcmp(s.main,"MSP430F5529")) return false;
    if(strcmp(s.link,"UP") && strcmp(s.link,"STALE") && strcmp(s.link,"NOT_CONNECTED")) return false;
    if(s.hasTelemetry && !direct::status(s.telemetry)) return false;
    if(s.fresh && (!s.hasAge || s.age>=3500u || !s.hasTelemetry || strcmp(s.link,"UP"))) return false;
    result=s; return true;
}
struct HttpResponse {
    char buffer[3072]{};
    size_t used=0,bodyAt=0,length=0;
    bool bad=false,headers=false;
    void reset() { used=bodyAt=length=0; bad=headers=false; buffer[0]=0; }
    static bool equalHeader(const char *p,const char *end,const char *expected) {
        while(*expected && p<end) {
            char c=*p++; if(c>='A' && c<='Z') c+=32;
            if(c!=*expected++) return false;
        }
        return !*expected && p==end;
    }
    bool complete() const { return !bad && headers && used==bodyAt+length; }
    const char *body() const { return buffer+bodyAt; }
    void feed(const char *data,size_t n) {
        if(bad) return;
        if(memchr(data,0,n)) { bad=true; return; }
        if(n>=sizeof(buffer)-used) { bad=true; return; }
        memcpy(buffer+used,data,n); used+=n; buffer[used]=0;
        if(!headers) {
            const char *end=strstr(buffer,"\r\n\r\n");
            if(!end) { if(used>1024) bad=true; return; }
            bodyAt=static_cast<size_t>(end-buffer)+4;
            if(bodyAt>1024 || (strncmp(buffer,"HTTP/1.1 200 ",13) && strncmp(buffer,"HTTP/1.0 200 ",13))) { bad=true; return; }
            const char *p=strstr(buffer,"\r\n")+2;
            bool found=false;
            while(p<end) {
                const char *e=strstr(p,"\r\n"),*colon=static_cast<const char *>(memchr(p,':',e-p));
                if(!colon) { bad=true; return; }
                if(equalHeader(p,colon,"transfer-encoding")) { bad=true; return; }
                if(equalHeader(p,colon,"content-length")) {
                    if(found) { bad=true; return; }
                    const char *v=colon+1; while(v<e && (*v==' ' || *v=='\t')) ++v;
                    char digits[12]; size_t count=static_cast<size_t>(e-v);
                    if(count==0 || count>=sizeof(digits)) { bad=true; return; }
                    memcpy(digits,v,count); digits[count]=0; uint32_t size=0;
                    if(!number(digits,size) || !size || size>1600) { bad=true; return; }
                    length=size; found=true;
                }
                p=e+2;
            }
            if(!found) { bad=true; return; }
            headers=true;
        }
        if(used>bodyAt+length) bad=true;
    }
};
}
