#include <Arduino.h>
#include "esp_camera.h"
#include <cstring>

// XIAO ESP32-S3 + Sense camera expansion. Pin map matches the installed
// Espressif CameraWebServer CAMERA_MODEL_XIAO_ESP32S3 definition.
// Continuous USB JPEG stream. The laptop relays it as MJPEG; no Wi-Fi or robot outputs.
static bool cameraReady=false;
static bool streaming=false;
static uint32_t lastFrameMs=0;
static esp_err_t cameraError=ESP_FAIL;
static char line[32];
static size_t used=0;
static bool discard=false;

static uint32_t crc32(const uint8_t *data,size_t size) {
    uint32_t crc=0xffffffffu;
    while(size--) {
        crc^=*data++;
        for(unsigned i=0;i<8;++i) crc=(crc>>1)^((crc&1)?0xedb88320u:0u);
    }
    return ~crc;
}
static const char *sensorName(uint16_t pid) {
    switch(pid) {
    case OV2640_PID:return "OV2640";
    case OV3660_PID:return "OV3660";
    case OV5640_PID:return "OV5640";
    default:return "OTHER";
    }
}
static void info() {
    sensor_t *sensor=cameraReady?esp_camera_sensor_get():nullptr;
    const uint16_t pid=sensor?sensor->id.PID:0;
    Serial.printf("INFO BOARD=XIAO_ESP32S3 FW=CAMERA_USB_V2 CAMERA_READY=%u SENSOR=%s PID=0x%04X PSRAM_BYTES=%u FRAME=QVGA WIFI=OFF STREAM=%s ERROR=0x%X\n",
                  cameraReady?1u:0u,sensorName(pid),pid,ESP.getPsramSize(),streaming?"ON":"OFF",static_cast<unsigned>(cameraError));
}
static void capture() {
    if(!cameraReady) { Serial.println("ERROR CAMERA_NOT_READY"); return; }
    camera_fb_t *frame=esp_camera_fb_get();
    if(!frame) { Serial.println("ERROR CAPTURE_FAILED"); return; }
    if(frame->format!=PIXFORMAT_JPEG || frame->len<4 || frame->len>512u*1024u) {
        esp_camera_fb_return(frame); Serial.println("ERROR INVALID_FRAME"); return;
    }
    Serial.printf("FRAME TYPE=JPEG BYTES=%u CRC32=%08lX WIDTH=%u HEIGHT=%u\n",
                  static_cast<unsigned>(frame->len),static_cast<unsigned long>(crc32(frame->buf,frame->len)),
                  static_cast<unsigned>(frame->width),static_cast<unsigned>(frame->height));
    size_t sent=0; const uint32_t start=millis();
    while(Serial && sent<frame->len && static_cast<uint32_t>(millis()-start)<1500u) {
        const size_t remain=frame->len-sent;
        sent+=Serial.write(frame->buf+sent,remain>512?512:remain);
        yield();
    }
    const bool complete=sent==frame->len;
    esp_camera_fb_return(frame);
    if(complete) Serial.print("\nEND FRAME\n");
    else { streaming=false; Serial.print("\nERROR USB_FRAME_TIMEOUT\n"); }
}
static void command() {
    line[used]=0;
    if(!strcmp(line,"PING")) Serial.println("PONG XIAO_CAMERA_USB_V2");
    else if(!strcmp(line,"INFO")) info();
    else if(!strcmp(line,"STREAM_START")) {
        if(cameraReady) { streaming=true; lastFrameMs=millis()-50u; Serial.println("OK STREAM_START"); }
        else Serial.println("ERROR CAMERA_NOT_READY");
    }
    else if(!strcmp(line,"STREAM_STOP")) { streaming=false; Serial.println("OK STREAM_STOP"); }
    else if(!strcmp(line,"HELP")) Serial.println("PING | INFO | STREAM_START | STREAM_STOP. USB video only.");
    else Serial.println("ERROR UNKNOWN_COMMAND");
}
void setup() {
    Serial.begin(115200);
    Serial.setTxTimeoutMs(100);
    const uint32_t start=millis();
    while(!Serial && static_cast<uint32_t>(millis()-start)<2000u) delay(10);
    camera_config_t config={};
    config.ledc_channel=LEDC_CHANNEL_0; config.ledc_timer=LEDC_TIMER_0;
    config.pin_d0=15; config.pin_d1=17; config.pin_d2=18; config.pin_d3=16;
    config.pin_d4=14; config.pin_d5=12; config.pin_d6=11; config.pin_d7=48;
    config.pin_xclk=10; config.pin_pclk=13; config.pin_vsync=38; config.pin_href=47;
    config.pin_sccb_sda=40; config.pin_sccb_scl=39;
    config.pin_pwdn=-1; config.pin_reset=-1;
    config.xclk_freq_hz=20000000; config.pixel_format=PIXFORMAT_JPEG;
    config.frame_size=FRAMESIZE_QVGA; config.jpeg_quality=12;
    config.fb_count=psramFound()?2:1;
    config.grab_mode=CAMERA_GRAB_LATEST;
    config.fb_location=psramFound()?CAMERA_FB_IN_PSRAM:CAMERA_FB_IN_DRAM;
    cameraError=esp_camera_init(&config); cameraReady=cameraError==ESP_OK;
    Serial.println("XIAO camera USB live relay ready; send STREAM_START");
    info();
}
void loop() {
    for(unsigned n=0;n<64 && Serial.available();++n) {
        const int c=Serial.read();
        if(c=='\r') continue;
        if(c=='\n') {
            if(discard) Serial.println("ERROR INVALID_LINE");
            else if(used) command();
            used=0; discard=false;
        } else if(!discard) {
            if(c<32 || c>126 || used+1>=sizeof(line)) { used=0; discard=true; }
            else line[used++]=static_cast<char>(c);
        }
    }
    if(!Serial) streaming=false;
    if(streaming && static_cast<uint32_t>(millis()-lastFrameMs)>=50u) {
        lastFrameMs=millis();
        capture();
    }
    delay(1);
}
