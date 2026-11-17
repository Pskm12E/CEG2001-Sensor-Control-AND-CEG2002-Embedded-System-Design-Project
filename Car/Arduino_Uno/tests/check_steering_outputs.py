"""Check real integrated sensor decisions through the sketch's GPIO output code."""
from pathlib import Path
import re
import subprocess

project = Path(__file__).resolve().parents[1]
source = (project / 'msp_line_follow/msp_line_follow.ino').read_text(encoding='utf-8')
settings = '\n'.join(re.findall(r'^const (?:bool|uint8_t|uint32_t) (?:LEFT_IR_PIN.*|LEFT_FORWARD_IN1_HIGH.*|REVERSE_TURN_OUTPUTS.*|TURN_LIMIT_MS.*)$', source, re.M))
drive = source[source.index('void applyDrive() {'):source.index('void statusUsb() {')]
controller = re.search(r'^RobotControl robot\([^;]+;', source, re.M).group(0)
build = project / 'build/steering_output_tests'
build.mkdir(parents=True, exist_ok=True)
harness = r'''
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include "../../msp_line_follow/control.h"
const uint8_t LED_BUILTIN=13, A0=14, A1=15;
int gpio[20]={};
void digitalWrite(uint8_t pin,bool value) { gpio[pin]=value; }
int digitalRead(uint8_t pin) { return gpio[pin]; }
int analogRead(uint8_t pin) { return gpio[pin]; }
SETTINGS
CONTROLLER
DRIVE
unsigned checks=0;
void check(bool ok,const char* message) {
    ++checks;
    if(!ok) { std::fprintf(stderr,"FAIL: %s\n",message); std::exit(1); }
}
void wheels(bool left,bool right,const char* message) {
    check(gpio[7]==left && !gpio[8] && gpio[9]==right && !gpio[10],message);
}
RlPacket deliver(const RlPacket& request,uint32_t now) {
    uint8_t frame[RL_SIZE]; rlEncode(&request,frame);
    RlParser parser={}; RlPacket received={}; int result=0;
    for(uint8_t byte:frame) result=rlFeed(&parser,byte,&received);
    check(result==1,"MSP command reaches controller through a valid frame");
    return robot.handle(received,now);
}
void sample(uint32_t now,uint16_t left,uint16_t right) {
    // User-confirmed physical wires, independent of the sketch's pin constants.
    // A0/A1 remain zero: reading the old unwired pins must fail this test.
    gpio[4]=left; gpio[2]=right;
    sampleLineSensors(now); applyDrive();
    sampleLineSensors(now+9); applyDrive();
}
void begin(uint32_t& now,uint16_t leftWhite,uint16_t rightWhite) {
    RlPacket hello={RL_HELLO,0x430,0,0,0}; deliver(hello,now);
    applyDrive(); wheels(false,false,"HELLO keeps both wheels stopped");
    RlPacket w={RL_WHITE,0x430,1,0,0}; deliver(w,now);
    for(unsigned i=0;i<40;++i) { now+=5; gpio[4]=leftWhite; gpio[2]=rightWhite; sampleLineSensors(now); applyDrive(); }
    RlPacket b={RL_BLACK,0x430,2,0,0}; deliver(b,now);
    for(unsigned i=0;i<40;++i) { now+=5; gpio[4]=1-leftWhite; gpio[2]=1-rightWhite; sampleLineSensors(now); applyDrive(); }
    check(robot.sensors[0].white==leftWhite && robot.sensors[1].white==rightWhite,"D4/D2 white captures match the physical sensor outputs");
    check(robot.sensors[0].black==1-leftWhite && robot.sensors[1].black==1-rightWhite,"D4/D2 black captures retain independent digital polarity");
    sample(now+10,leftWhite,rightWhite); now+=20;
    RlPacket start={RL_START,0x430,3,0,0};
    check(deliver(start,now).detail==RL_OK,"MSP authorises calibrated digital start");
    applyDrive(); wheels(true,true,"white/white drives both wheels forward");
}
void capture(uint8_t op,uint16_t sequence,uint32_t& now,int left,int right,bool noisyLeft=false) {
    RlPacket request={op,0x430,sequence,0,0};
    check(deliver(request,now).detail==RL_OK,"MSP authorises digital calibration capture");
    for(unsigned i=0;i<40;++i) {
        now+=5; gpio[4]=noisyLeft?i%2:left; gpio[2]=right;
        sampleLineSensors(now); applyDrive();
        check(!robot.following && !gpio[7] && !gpio[8] && !gpio[9] && !gpio[10],
              "digital calibration holds both motors stopped throughout sampling");
    }
}
int main() {
    uint32_t now=0;
    for(uint8_t lw=0;lw<2;++lw) for(uint8_t rw=0;rw<2;++rw) {
        const uint16_t wl=lw, wr=rw;
        begin(now,wl,wr);
        sample(now+20,1-wl,wr);
        check(robot.action==DRIVE_RIGHT,"physical left D4 black requests a right turn away from the border");
        wheels(true,false,"left BLACK: LEFT wheel forward, RIGHT wheel stopped -> turn RIGHT");
        sample(now+40,wl,wr);
        wheels(true,true,"recentring on white restores forward");
        sample(now+60,wl,1-wr);
        check(robot.action==DRIVE_LEFT,"physical right D2 black requests a left turn away from the border");
        wheels(false,true,"right BLACK: LEFT wheel stopped, RIGHT wheel forward -> turn LEFT");
        RlPacket stop={RL_STOP,0x430,4,0,0};
        deliver(stop,now+75); applyDrive();
        wheels(false,false,"MSP STOP overrides corner outputs");
        sample(now+80,wl,wr);
        wheels(false,false,"clear/white input cannot restart after STOP");
        now+=100;
        begin(now,wl,wr);
        sample(now+20,1-wl,1-wr);
        check(!robot.following && robot.reason==RL_BOTH_BLACK,"both black latches a stop");
        wheels(false,false,"both black stops both motor channels");
        now+=100;
    }
    RlPacket hello={RL_HELLO,0x430,0,0,0}; deliver(hello,now);
    capture(RL_WHITE,1,now,0,1);
    capture(RL_BLACK,2,now,1,1);
    check(robot.sensors[0].calibrated() && !robot.sensors[1].calibrated(),
          "one identical digital output refuses overall calibration");
    sample(now+10,0,1); now+=20;
    RlPacket start={RL_START,0x430,3,0,0};
    check(deliver(start,now).detail==RL_NOT_CAL,"SAME digital output refuses MSP start");
    applyDrive(); wheels(false,false,"SAME calibration keeps both motor channels off");

    deliver(hello,now);
    capture(RL_WHITE,1,now,0,0,true);
    check(robot.reason==RL_CAL_UNSTABLE && robot.sensors[0].white==-1,
          "switching digital input rejects noisy white capture");
    capture(RL_BLACK,2,now,1,1);
    sample(now+10,0,0); now+=20;
    check(deliver(start,now).detail==RL_NOT_CAL,"noisy missing capture refuses MSP start");
    applyDrive(); wheels(false,false,"noisy calibration keeps both motor channels off");
    std::printf("PASS %u sensor-to-GPIO steering assertions across both sensor polarities.\n",checks);
}
'''.replace('SETTINGS', settings).replace('CONTROLLER', controller).replace('DRIVE\n', drive+'\n')
test_source = build / 'steering_outputs.cpp'
test_source.write_text(harness, encoding='utf-8')
exe = build / 'steering_outputs.exe'
subprocess.run([r'C:\msys64\ucrt64\bin\g++.exe','-std=c++11','-Wall','-Wextra','-Werror',
                '-static',str(test_source),'-o',str(exe)], check=True)
subprocess.run([str(exe)], check=True)
