"""Exercise the actual USB report with the Uno's 63-byte usable TX buffer."""
from pathlib import Path
import subprocess

root = Path(__file__).resolve().parents[1]
source = (root / 'msp_line_follow/msp_line_follow.ino').read_text(encoding='utf-8')
start = source.index('const char* calibrationLabel(') if 'const char* calibrationLabel(' in source else source.index('void statusUsb() {')
report = source[start:source.index('void readUsb() {')]
build = root / 'build/ir_report_tests'
build.mkdir(parents=True, exist_ok=True)
harness = r'''
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <string>
#include "../../msp_line_follow/control.h"
struct FakeSerial {
    int freeBytes=63;
    std::string output;
    int availableForWrite() const { return freeBytes; }
    void write(const uint8_t* data,int count) {
        if(count>freeBytes || count>63) std::exit(2);
        output.append(reinterpret_cast<const char*>(data),count);
    }
} Serial;
RobotControl robot(WHITE_LANE,3000);
uint8_t usbReportPart=0;
REPORT
unsigned checks=0;
void check(bool ok,const char* text) {
    ++checks;
    if(!ok) { std::fprintf(stderr,"FAIL: %s\n",text); std::exit(1); }
}
int main() {
    robot.sensors[0].raw=1; robot.sensors[0].white=0; robot.sensors[0].black=1;
    robot.sensors[1].raw=0; robot.sensors[1].white=0; robot.sensors[1].black=0;
    statusUsb(); statusUsb(); statusUsb();
    check(Serial.output.find("CAL=0")!=std::string::npos,"overall contrast failure remains visible");
    check(Serial.output.find("IR LEFT D4 RAW=1 W=0 B=1 OK\n")!=std::string::npos,"show actual left digital value and physical D4 pin");
    check(Serial.output.find("IR RIGHT D2 RAW=0 W=0 B=0 SAME\n")!=std::string::npos,"show identical right samples on D2 without a false ready result");
    check(Serial.output.find(" T=")==std::string::npos,"digital reporting does not invent an ADC threshold");
    check(!robot.following && robot.action==DRIVE_STOP,"reporting cannot start motors");
    Serial.output.clear(); usbReportPart=1;
    robot.sensors[0].white=robot.sensors[0].black=-1;
    robot.sensors[0].raw=1;
    Serial.freeBytes=0; statusUsb();
    check(Serial.output.empty() && usbReportPart==1,"full buffer skips without losing diagnostic turn");
    Serial.freeBytes=63; statusUsb();
    check(Serial.output.find("IR LEFT D4 RAW=1 W=-1 B=-1 MISSING\n")!=std::string::npos,"absent/unstable samples explicit on physical digital pin");
    check(Serial.output.size()<=63 && usbReportPart==2,"largest real report fits Uno TX space");
    Serial.output.clear(); usbReportPart=1;
    robot.sensors[0].raw=0; robot.sensors[0].white=1; robot.sensors[0].black=0;
    robot.sensors[1].raw=1; robot.sensors[1].white=0; robot.sensors[1].black=1;
    statusUsb(); statusUsb(); statusUsb();
    check(Serial.output.find("CAL=1")!=std::string::npos,"opposite valid sensor polarities both calibrate");
    check(Serial.output.find("SAME")==std::string::npos,"valid polarity not labelled identical");
    check(Serial.output.find("IR LEFT D4 RAW=0 W=1 B=0 OK\n")!=std::string::npos &&
          Serial.output.find("IR RIGHT D2 RAW=1 W=0 B=1 OK\n")!=std::string::npos,
          "both independent digital polarities report their actual levels");
    Serial.output.clear(); usbReportPart=1;
    Serial.freeBytes=10; statusUsb();
    check(Serial.output.empty() && usbReportPart==1,"partly full buffer also skips without blocking or advancing");
    Serial.freeBytes=63; statusUsb();
    check(!Serial.output.empty() && usbReportPart==2,"report resumes when enough buffer space returns");
    Serial.output.clear(); usbReportPart=0;
    robot.reason=255; robot.userRequest=255;
    statusUsb();
    check(Serial.output.size()<=63 && !Serial.output.empty(),"largest digital summary fits Uno TX space");
    check(!robot.following && robot.action==DRIVE_STOP,"all diagnostic cases leave movement stopped");
    std::printf("PASS %u real USB reporting assertions.\n",checks);
}
'''.replace('REPORT', report)
cpp = build / 'ir_report.cpp'
cpp.write_text(harness, encoding='utf-8')
exe = build / 'ir_report.exe'
subprocess.run(['C:/msys64/ucrt64/bin/g++.exe','-std=c++11','-Wall','-Wextra','-Wno-unused-function','-Werror','-static',str(cpp),'-o',str(exe)],check=True)
subprocess.run([str(exe)],check=True)
