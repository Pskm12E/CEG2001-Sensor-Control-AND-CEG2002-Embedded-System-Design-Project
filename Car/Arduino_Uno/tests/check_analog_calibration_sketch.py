"""Run the actual sensor-only sketch with fake ADC/USB, without a board."""
from pathlib import Path
import subprocess

root=Path(__file__).resolve().parents[1]
build=root/'build/analog_calibration_tests'
build.mkdir(parents=True,exist_ok=True)
(build/'Arduino.h').write_text(r'''
#pragma once
#include <cstdint>
#include <cstdlib>
#include <string>
#include <algorithm>
#define HIGH 1
#define LOW 0
#define INPUT 0
#define OUTPUT 1
#define F(s) s
const uint8_t A0=14,A1=15,LED_BUILTIN=13;
extern uint32_t clockMs;
extern int levels[20],adc[20],jitter,reads;
inline uint32_t millis(){ return clockMs; }
inline void delay(unsigned long ms){ clockMs+=ms; }
inline void pinMode(uint8_t,int){}
inline void digitalWrite(uint8_t p,int v){ levels[p]=v; }
inline int analogRead(uint8_t p){ ++reads; return adc[p]+(jitter && (reads/8)%2 ? jitter:0); }
struct TestSerial {
 std::string input,output;
 void begin(unsigned long){}
 int available(){ return int(input.size()); }
 int read(){ int c=input.front(); input.erase(0,1); return c; }
 void print(const char* s){ output+=s; }
 void print(int n){ output+=std::to_string(n); }
 void println(const char* s){ print(s); output+='\n'; }
 void println(int n){ print(n); output+='\n'; }
};
extern TestSerial Serial;
''',encoding='utf-8')
harness=r'''
#include <Arduino.h>
#include <cstdio>
uint32_t clockMs=0;
int levels[20]={},adc[20]={},jitter=0,reads=0;
TestSerial Serial;
#include "../../ir_analog_calibration/ir_analog_calibration.ino"
unsigned checks=0;
void check(bool ok,const char* message){
 ++checks; if(!ok){std::fprintf(stderr,"FAIL: %s\n",message); std::exit(1);}
}
bool stopped(){return !levels[7]&&!levels[8]&&!levels[9]&&!levels[10];}
void command(const char* c){Serial.input=c;loop();check(stopped(),"every USB command keeps motor pins LOW");}
void surface(int l,int r){adc[A0]=l;adc[A1]=r;reads=0;}
int main(){
 setup(); check(stopped(),"startup has no driving output");
 check(sensitivity==70,"V3 starts with the requested more sensitive threshold");
 check(Serial.output.find("CALIBRATION V3")!=std::string::npos,"version banner identifies uploaded sensitivity build");
 command("sense 75\n");
 check(!calibrated(0)&&!calibrated(1),"sensitivity alone cannot invent missing captures");
 surface(200,650); command("white\n");
 check(whiteValue[0]==200&&whiteValue[1]==650,"full word white captures actual ADC means");
 surface(650,100); command("black\n");
 check(calibrated(0)&&calibrated(1),"full word black must NOT execute its internal c as clear");
 check(whiteValue[0]==200&&blackValue[0]==650,"word command preserves prior white capture");
 check(Serial.output.find("SPREAD=")!=std::string::npos,"capture reports the measured noise range");
 command("clear\n"); check(!calibrated(0)&&whiteValue[0]==-1&&blackValue[0]==-1,"explicit clear resets captures");
 check(Serial.output.find("NEED_w")!=std::string::npos,"unattempted sample is not falsely called unstable");
 surface(200,600); command("W\r\n");
 surface(650,100); command("B\r\n");
 check(calibrated(0)&&calibrated(1),"single-letter uppercase commands and CRLF work");
 command("this command contains black and clear\n");
 check(calibrated(0)&&calibrated(1),"overlong unknown text never runs embedded calibration or clear commands");
 command("status\n");check(calibrated(0),"read-only status preserves samples");
 command("c\n"); surface(200,600); jitter=80; command("w\n");
 check(whiteValue[0]==-1,"noisy capture stays invalid, no loosening acceptance");
 check(Serial.output.find("WHITE_NOISY")!=std::string::npos,"noise rejection differs from no command received");
 jitter=0;surface(200,600);command("w\n");
 surface(220,620);command("b\n");check(!calibrated(0)&&!calibrated(1),"insufficient real contrast remains rejected");
 check(Serial.output.find("GAP=20")!=std::string::npos,"weak contrast reports its measured gap");
 surface(200,600);command("w\n");surface(600,200);command("b\n");
 surface(350,450);command("sense 50\n");
 check(thresholdFor(0)==400&&thresholdFor(1)==400,"normal setting uses both midpoints");
 check(known[0]&&known[1]&&!blackNow[0]&&!blackNow[1],"test edge stays white at midpoint for both polarities");
 command("sense 70\n");
 check(thresholdFor(0)==320&&thresholdFor(1)==480,"higher sensitivity shifts both thresholds towards actual white");
 check(known[0]&&known[1]&&blackNow[0]&&blackNow[1],"same RAW switches to black at higher sensitivity for both polarities");
 check(levels[LED_BUILTIN]==HIGH,"Uno indicator reacts to black detection");
 check(whiteValue[0]==200&&blackValue[0]==600&&whiteValue[1]==600&&blackValue[1]==200,"sensitivity preserves real calibration samples");
 command("+\n");command("+\n");check(sensitivity==75,"plus clamps at upper limit");
 command("-\n");check(sensitivity==70,"minus lowers sensitivity by five");
 command("sense 24\n");command("sense 76\n");command("sense 30x\n");command("sense -1\n");
 check(sensitivity==70,"invalid sensitivity commands do not change the setting");
 command("sense 25\n");command("-\n");check(sensitivity==25,"minus clamps at lower limit");
 // Endpoints must stay reachable, even at the smallest accepted contrast.
 for(int setting:{25,75}){
   surface(200,240);command("w\n");surface(240,200);command("b\n");
   setSensitivity(setting);surface(200,240);report();
   check(known[0]&&known[1]&&!blackNow[0]&&!blackNow[1],"white endpoints remain white at sensitivity limits");
   surface(240,200);report();
   check(known[0]&&known[1]&&blackNow[0]&&blackNow[1],"black endpoints remain black at sensitivity limits");
 }
 surface(0,1023);command("w\n");surface(1023,0);command("b\n");
 command("sense 50\n");
 check(thresholdFor(0)==511&&thresholdFor(1)==512,"full ADC range thresholds avoid 16-bit multiplication overflow on Uno");
 command("clear\n");
 check(!levels[LED_BUILTIN]&&!calibrated(0),"clear cannot leave a false detection lit");
 std::printf("PASS %u actual analogue-calibration sensitivity/parser/capture/GPIO assertions.\n",checks);
}
'''
cpp=build/'calibration_sketch.cpp';cpp.write_text(harness,encoding='utf-8')
exe=build/'calibration_sketch.exe'
subprocess.run(['C:/msys64/ucrt64/bin/g++.exe','-std=c++11','-Wall','-Wextra','-Werror','-static','-I',str(build),str(cpp),'-o',str(exe)],check=True)
subprocess.run([str(exe)],check=True)
