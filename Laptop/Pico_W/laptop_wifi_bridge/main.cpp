#include <cstdio>
#include <cstring>
#include "pico/stdlib.h"
#include "pico/cyw43_arch.h"
#include "pico/stdio_usb.h"
#include "lwip/tcp.h"
#include "RobotBench.h"
#include "NetworkConfig.h"
#include "bridge_response.h"
#include "video_receiver.h"

// Desk Pico: USB <-> HTTP status over private Wi-Fi. No GPIO wires or actuator
// commands. The robot ESP32 owns the AP and UART bridge to the main MSP430.
static tcp_pcb *connection=nullptr;
static desk::HttpResponse response;
static desk::State remote;
static bench::Line<64> usbLine;
enum class Reply { None, Ping, State, Msp };
static Reply wanted=Reply::None;
static bool done=false,failed=false,haveState=false;
static uint32_t started=0,lastAttempt=0,lastGood=0,lastWifi=0,lastRenew=0;
static bool attempted=false,wifiAttempted=false;
// lwIP's initial TCP retransmission timeout is 3 s. Allow that retry to occur;
// an equal 3 s application deadline aborted otherwise recoverable reads.
static constexpr uint32_t HTTP_TIMEOUT_MS=8000u;
static unsigned goodReads=0,failedReads=0;
static int tcpError=0;
static const char *fault="NONE";
static const char *lastFault="NONE";
static int lastTcpError=0;
static char lastFailure[3072]{};
static size_t failedBytes=0,failedBody=0,failedLength=0;
static uint32_t nowMs() { return to_ms_since_boot(get_absolute_time()); }
static bool wifiUp();
static tcp_pcb *videoConnection=nullptr;
static video::Receiver videoFrames;
static bool videoWanted=false,videoConnected=false,videoBad=false;
static uint32_t videoAttempt=0,videoSeen=0;
static void closeVideo() {
    if(videoConnection) {
        tcp_arg(videoConnection,nullptr);tcp_recv(videoConnection,nullptr);tcp_err(videoConnection,nullptr);
        if(tcp_close(videoConnection)!=ERR_OK) tcp_abort(videoConnection);
        videoConnection=nullptr;
    }
    videoConnected=false;videoBad=false;videoFrames.reset();
}
static err_t videoReceived(void *,tcp_pcb *pcb,pbuf *p,err_t error) {
    if(!p) { videoBad=true;return ERR_OK; }
    if(error!=ERR_OK) { pbuf_free(p);videoBad=true;return ERR_OK; }
    tcp_recved(pcb,p->tot_len);
    for(pbuf *part=p;part;part=part->next)
        videoFrames.feed(static_cast<const uint8_t *>(part->payload),part->len);
    pbuf_free(p);videoSeen=nowMs();
    if(videoFrames.bad) videoBad=true;
    return ERR_OK;
}
static void videoError(void *,err_t) { videoConnection=nullptr;videoConnected=false;videoBad=true; }
static err_t videoOpened(void *,tcp_pcb *pcb,err_t error) {
    if(error!=ERR_OK) { videoBad=true;return ERR_OK; }
    tcp_nagle_disable(pcb);videoConnected=true;videoSeen=nowMs();return ERR_OK;
}
static void serviceVideo(uint32_t now) {
    if(!videoWanted || !stdio_usb_connected() || !wifiUp()) { closeVideo();return; }
    if(videoBad || (videoConnection && static_cast<uint32_t>(now-videoSeen)>5000u)) closeVideo();
    if(!videoConnection && static_cast<uint32_t>(now-videoAttempt)>=2000u) {
        videoAttempt=videoSeen=now;
        videoConnection=tcp_new_ip_type(IPADDR_TYPE_V4);
        if(videoConnection) {
            tcp_recv(videoConnection,videoReceived);tcp_err(videoConnection,videoError);
            ip_addr_t address;ipaddr_aton("192.168.4.10",&address);
            if(tcp_connect(videoConnection,&address,4243,videoOpened)!=ERR_OK) videoBad=true;
        }
    }
    if(videoFrames.ready) {
        // Main loop is the only USB writer. Finish each binary frame before any text reply.
        printf("VIDEO_FRAME BYTES=%u CRC32=%08lX SEQ=%lu\n",static_cast<unsigned>(videoFrames.length),
               static_cast<unsigned long>(videoFrames.checksum),static_cast<unsigned long>(videoFrames.sequence));
        stdio_put_string(reinterpret_cast<const char *>(videoFrames.jpeg),static_cast<int>(videoFrames.length),false,false);
        stdio_put_string("\nEND_VIDEO\n",11,false,false);
        videoFrames.ready=false;
    }
}
static bool wifiUp() { return cyw43_tcpip_link_status(&cyw43_state,CYW43_ITF_STA)==CYW43_LINK_UP; }
static bool espUp(uint32_t now) { return wifiUp() && haveState && static_cast<uint32_t>(now-lastGood)<2500u; }
static bool mspUp(uint32_t now) {
    const uint32_t elapsed=now-lastGood;
    return espUp(now) && remote.fresh && remote.hasAge && remote.age<3500u && elapsed<3500u-remote.age;
}
static void closeConnection() {
    if(!connection) return;
    tcp_arg(connection,nullptr); tcp_recv(connection,nullptr); tcp_err(connection,nullptr);
    if(tcp_close(connection)!=ERR_OK) tcp_abort(connection);
    connection=nullptr;
}
static void errorReply(const char *reason) {
    if(wanted!=Reply::None) printf("ROBOT ERROR %s\n",reason);
    wanted=Reply::None;
}
static err_t received(void *,tcp_pcb *pcb,pbuf *p,err_t error) {
    if(!p) { if(!response.complete()) { failed=true; fault="EARLY_CLOSE"; } done=true; return ERR_OK; }
    if(error!=ERR_OK) { pbuf_free(p); fault="RECEIVE_ERROR"; tcpError=error; failed=done=true; return ERR_OK; }
    tcp_recved(pcb,p->tot_len);
    for(pbuf *part=p;part;part=part->next)
        response.feed(static_cast<const char *>(part->payload),part->len);
    pbuf_free(p);
    if(response.bad) { fault="HTTP_FORMAT"; failed=done=true; }
    else if(response.complete()) done=true;
    return ERR_OK;
}
static void networkError(void *,err_t error) {
    connection=nullptr; tcpError=error;
    if(!response.complete()) { fault="TCP_ERROR"; failed=true; }
    done=true;
}
static err_t connected(void *,tcp_pcb *pcb,err_t error) {
    if(error!=ERR_OK) { failed=done=true; return ERR_OK; }
    static constexpr char request[]="GET /api/state HTTP/1.0\r\nHost: 192.168.4.1\r\nConnection: close\r\n\r\n";
    if(tcp_write(pcb,request,sizeof(request)-1,TCP_WRITE_FLAG_COPY)!=ERR_OK || tcp_output(pcb)!=ERR_OK)
        failed=done=true;
    return ERR_OK;
}
static bool beginRequest(Reply reply) {
    if(!wifiUp()) return false;
    if(connection) {
        // An existing read may fulfil one waiting USB request; no command queue.
        if(wanted!=Reply::None || reply==Reply::None) return false;
        wanted=reply; return true;
    }
    connection=tcp_new_ip_type(IPADDR_TYPE_V4);
    if(!connection) return false;
    wanted=reply; response.reset(); failed=done=false; fault="NONE"; tcpError=0;
    started=lastAttempt=nowMs(); attempted=true;
    tcp_recv(connection,received); tcp_err(connection,networkError);
    ip_addr_t address; ipaddr_aton("192.168.4.1",&address);
    if(tcp_connect(connection,&address,80,connected)!=ERR_OK) failed=done=true;
    return true;
}
static void finishRequest() {
    desk::State parsed;
    const bool ok=!failed && response.complete() && desk::state(response.body(),parsed);
    closeConnection(); done=false;
    if(!ok) {
        ++failedReads;
        if(!failed) fault="JSON_STATE";
        lastFault=fault; lastTcpError=tcpError;
        snprintf(lastFailure,sizeof(lastFailure),"%s",response.buffer);
        failedBytes=response.used; failedBody=response.bodyAt; failedLength=response.length;
        haveState=false; errorReply("ESP_UNAVAILABLE_OR_INVALID_RESPONSE"); return;
    }
    ++goodReads;
    remote=parsed; haveState=true; lastGood=nowMs();
    switch(wanted) {
    case Reply::Ping: printf("ROBOT PONG ESP32_DIRECT_WIFI_V1\n"); break;
    case Reply::State: printf("ROBOT STATE %s\n",response.body()); break;
    case Reply::Msp:
        if(mspUp(nowMs())) printf("ROBOT MSP %s\n",remote.telemetry);
        else printf("ROBOT ERROR MSP_NOT_FRESH\n");
        break;
    default: break;
    }
    wanted=Reply::None;
}
static void command(const char *line) {
    if(!strcmp(line,"VIDEO ON")) { videoWanted=true;videoAttempt=nowMs()-2000u;printf("VIDEO OK ON\n"); }
    else if(!strcmp(line,"VIDEO OFF")) { videoWanted=false;closeVideo();printf("VIDEO OK OFF\n"); }
    else if(!strcmp(line,"VIDEO STATUS")) printf("VIDEO STATUS LINK=%s FRAMES=%lu DROPPED=%lu CAMERA_IP=192.168.4.10 PORT=4243\n",
             videoConnected?"UP":"DOWN",static_cast<unsigned long>(videoFrames.frames),static_cast<unsigned long>(videoFrames.dropped));
    else if(!strcmp(line,"PING")) printf("PONG PICO_DESK_BRIDGE_V2\n");
    else if(!strcmp(line,"DIAG")) {
        printf("DIAG GOOD=%u FAIL=%u FAULT=%s TCP=%d USED=%u BODY_AT=%u LENGTH=%u\n",goodReads,failedReads,lastFault,lastTcpError,
               static_cast<unsigned>(failedBytes),static_cast<unsigned>(failedBody),static_cast<unsigned>(failedLength));
        printf("LAST_FAILED_RESPONSE ");
        for(const char *p=lastFailure;*p;++p) {
            if(*p=='\r') printf("\\r"); else if(*p=='\n') printf("\\n"); else putchar(*p);
        }
        printf("\n");
    }
    else if(!strcmp(line,"STATUS")) {
        const uint32_t now=nowMs();
        printf("STATUS BOARD=PICO_W ROLE=LAPTOP_BRIDGE FW=DESK_BRIDGE_V2 LED=ON WIFI=%s ESP_LINK=%s MSP_LINK=%s READ_ONLY=1\n",
               wifiUp()?"UP":"DOWN",espUp(now)?"UP":"DOWN",mspUp(now)?"UP":haveState?"STALE":"NOT_CONNECTED");
    } else if(!strcmp(line,"HELP") || !strcmp(line,"?"))
        printf("PING | STATUS | ROBOT PING | ROBOT STATE | ROBOT MSP STATUS. Read-only stage; no motion, spray, STOP or calibration commands.\n");
    else {
        Reply op=Reply::None;
        if(!strcmp(line,"ROBOT PING")) op=Reply::Ping;
        else if(!strcmp(line,"ROBOT STATE") || !strcmp(line,"STATE")) op=Reply::State;
        else if(!strcmp(line,"ROBOT MSP STATUS") || !strcmp(line,"MSP STATUS")) op=Reply::Msp;
        if(op==Reply::None) { printf("ERROR unsupported command; read-only bridge\n"); return; }
        if(!beginRequest(op)) printf("ROBOT ERROR WIFI_DOWN_OR_BUSY\n");
    }
}
int main() {
    stdio_init_all();
    stdio_set_translate_crlf(&stdio_usb,false);
    if(cyw43_arch_init()) while(true) { printf("ERROR wireless initialization failed\n"); sleep_ms(1000); }
    cyw43_arch_enable_sta_mode();
    cyw43_wifi_pm(&cyw43_state,CYW43_NONE_PM);
    cyw43_arch_gpio_put(CYW43_WL_GPIO_LED_PIN,1); // running indicator, not a Wi-Fi status LED
    printf("Pico W DESK_BRIDGE_V2; private Wi-Fi camera and read-only robot status relay\n");
    while(true) {
        cyw43_arch_poll();
        const uint32_t now=nowMs();
        if(!wifiUp()) {
            closeConnection(); errorReply("WIFI_DOWN");
            haveState=false; done=failed=false;
            if(!wifiAttempted || static_cast<uint32_t>(now-lastWifi)>=15000u) {
                wifiAttempted=true; lastWifi=now;
                cyw43_arch_wifi_connect_async(BENCH_SSID,BENCH_PASSWORD,CYW43_AUTH_WPA2_AES_PSK);
            }
        } else {
            if(connection && static_cast<uint32_t>(now-started)>=HTTP_TIMEOUT_MS) { fault="TIMEOUT"; failed=done=true; }
            if(done) finishRequest();
            if(!connection && (!attempted || static_cast<uint32_t>(now-lastAttempt)>=1000u)) beginRequest(Reply::None);
            // Renew association after an AP power cycle leaves a stale UP state.
            const uint32_t checkNow=nowMs();
            if(!espUp(checkNow) && static_cast<uint32_t>(checkNow-lastGood)>=15000u && static_cast<uint32_t>(checkNow-lastRenew)>=15000u) {
                closeConnection(); errorReply("WIFI_RECONNECTING");
                cyw43_arch_disable_sta_mode(); cyw43_arch_enable_sta_mode();
                cyw43_wifi_pm(&cyw43_state,CYW43_NONE_PM);
                cyw43_arch_gpio_put(CYW43_WL_GPIO_LED_PIN,1);
                wifiAttempted=false; haveState=false; done=failed=false; lastRenew=checkNow;
            }
        }
        for(unsigned n=0;n<128;++n) {
            const int c=getchar_timeout_us(0); if(c==PICO_ERROR_TIMEOUT) break;
            const auto result=usbLine.push(static_cast<uint8_t>(c));
            if(result==bench::Feed::Ready) command(usbLine.text);
            else if(result==bench::Feed::Invalid) printf("ERROR invalid or oversized USB line\n");
            if(result!=bench::Feed::Pending) usbLine.reset();
        }
        serviceVideo(nowMs());
        sleep_ms(1);
    }
}
