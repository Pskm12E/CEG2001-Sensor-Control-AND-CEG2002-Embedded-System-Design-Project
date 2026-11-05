#include <Arduino.h>
#include <WiFi.h>
#include <NetworkConfig.h>
#include "esp_camera.h"

// Car camera: joins the EXISTING FireBeetle private AP. USB is power/debug only.
// Dedicated camera TCP stream -> desk Pico -> laptop. No robot commands.
static WiFiServer videoServer(4243);
static WiFiClient viewer;
static bool ready=false;
static uint32_t frameSequence=0,lastFrame=0,lastReconnect=0;
static char commandLine[40];
static size_t commandUsed=0;
static uint32_t crc32(const uint8_t *data,size_t size) {
    uint32_t crc=0xffffffffu;
    while(size--) { crc^=*data++; for(unsigned n=0;n<8;++n) crc=(crc>>1)^((crc&1)?0xedb88320u:0u); }
    return ~crc;
}
static void little(uint8_t *p,uint32_t value) {
    for(unsigned n=0;n<4;++n) p[n]=static_cast<uint8_t>(value>>(8*n));
}
static void info() {
    Serial.printf("INFO BOARD=XIAO_ESP32S3 FW=CAMERA_WIFI_V1 CAMERA_READY=%u WIFI=%s IP=%s PORT=4243 USB_VIDEO=OFF FRAMES=%lu\n",
                  ready?1u:0u,WiFi.status()==WL_CONNECTED?"UP":"DOWN",WiFi.localIP().toString().c_str(),static_cast<unsigned long>(frameSequence));
}
void setup() {
    Serial.begin(115200);
    camera_config_t config={};
    config.ledc_channel=LEDC_CHANNEL_0;config.ledc_timer=LEDC_TIMER_0;
    config.pin_d0=15;config.pin_d1=17;config.pin_d2=18;config.pin_d3=16;
    config.pin_d4=14;config.pin_d5=12;config.pin_d6=11;config.pin_d7=48;
    config.pin_xclk=10;config.pin_pclk=13;config.pin_vsync=38;config.pin_href=47;
    config.pin_sccb_sda=40;config.pin_sccb_scl=39;config.pin_pwdn=-1;config.pin_reset=-1;
    config.xclk_freq_hz=20000000;config.pixel_format=PIXFORMAT_JPEG;
    config.frame_size=FRAMESIZE_QVGA;config.jpeg_quality=14;
    config.fb_count=psramFound()?2:1;config.grab_mode=CAMERA_GRAB_LATEST;
    config.fb_location=psramFound()?CAMERA_FB_IN_PSRAM:CAMERA_FB_IN_DRAM;
    ready=esp_camera_init(&config)==ESP_OK;
    WiFi.mode(WIFI_STA);WiFi.setSleep(false);
    WiFi.config(IPAddress(192,168,4,10),IPAddress(192,168,4,1),IPAddress(255,255,255,0));
    WiFi.begin(BENCH_SSID,BENCH_PASSWORD);
    videoServer.begin();
    info();
}
void loop() {
    while(Serial.available()) {
        const int c=Serial.read();
        if(c=='\n') {
            commandLine[commandUsed]=0;
            if(!strcmp(commandLine,"PING")) Serial.println("PONG XIAO_CAMERA_WIFI_V1");
            else if(!strcmp(commandLine,"INFO")) info();
            else Serial.println("ERROR USB debug only; video uses private Wi-Fi");
            commandUsed=0;
        } else if(c!='\r') {
            if(c>=32 && c<=126 && commandUsed+1<sizeof(commandLine)) commandLine[commandUsed++]=static_cast<char>(c);
            else commandUsed=0;
        }
    }
    const uint32_t now=millis();
    if(WiFi.status()!=WL_CONNECTED) {
        viewer.stop();
        if(now-lastReconnect>10000u) { lastReconnect=now;WiFi.reconnect(); }
        delay(5);return;
    }
    if(!viewer || !viewer.connected()) {
        viewer.stop();viewer=videoServer.accept();
        if(viewer) viewer.setNoDelay(true);
        delay(1);return;
    }
    // The TCP endpoint accepts only one desk Pico viewer, no command payloads.
    while(viewer.available()) viewer.read();
    if(!ready || now-lastFrame<66u) { delay(1);return; }
    lastFrame=now;
    camera_fb_t *frame=esp_camera_fb_get();
    if(!frame) { delay(5);return; }
    if(frame->format==PIXFORMAT_JPEG && frame->len>=4 && frame->len<=32768u) {
        uint8_t header[16]={'P','C','V','1'};
        little(header+4,static_cast<uint32_t>(frame->len));
        little(header+8,crc32(frame->buf,frame->len));little(header+12,++frameSequence);
        bool good=viewer.write(header,sizeof(header))==sizeof(header);
        size_t offset=0;const uint32_t begin=millis();
        while(good && offset<frame->len && millis()-begin<1500u) {
            const size_t length=min(static_cast<size_t>(1460),frame->len-offset);
            const size_t sent=viewer.write(frame->buf+offset,length);
            if(!sent) good=false;
            offset+=sent;yield();
        }
        if(!good || offset!=frame->len) viewer.stop();
    }
    esp_camera_fb_return(frame);
}
