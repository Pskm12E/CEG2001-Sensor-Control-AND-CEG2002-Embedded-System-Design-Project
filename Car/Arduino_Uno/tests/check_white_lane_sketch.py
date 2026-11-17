"""Run the actual Arduino-only white-road sketch using fake GPIO/serial."""
from pathlib import Path
import subprocess

project = Path(__file__).resolve().parents[1]
build = project / "build" / "white_lane_tests"
build.mkdir(parents=True, exist_ok=True)
(build / "Arduino.h").write_text(r'''
#pragma once
#include <cstdint>
#include <cstddef>
#include <string>
#define HIGH 1
#define LOW 0
#define INPUT 0
#define OUTPUT 1
#define F(value) value
extern uint32_t testMillis;
extern int gpio[20];
inline uint32_t millis() { return testMillis; }
inline void delay(uint32_t delta) { testMillis += delta; }
inline void pinMode(uint8_t, uint8_t) {}
inline int digitalRead(uint8_t pin) { return gpio[pin]; }
inline void digitalWrite(uint8_t pin, int value) { gpio[pin] = value; }
struct TestSerial {
  std::string input, output;
  void begin(unsigned long) {}
  int available() { return static_cast<int>(input.size()); }
  int read() { int c = input.front(); input.erase(0, 1); return c; }
  int availableForWrite() { return 128; }
  void print(const char* value) { output += value; }
  void println(const char* value) { output += value; output += '\n'; }
  void println(int8_t value) { output += std::to_string(static_cast<int>(value)); output += '\n'; }
  void println(uint32_t value) { output += std::to_string(value); output += '\n'; }
  void write(const uint8_t* data, size_t count) { output.append(reinterpret_cast<const char*>(data), count); }
};
extern TestSerial Serial;
''', encoding="utf-8")

harness = r'''
#include <Arduino.h>
#include <cstdlib>
#include <iostream>
uint32_t testMillis = 0;
int gpio[20] = {};
TestSerial Serial;
#include "../line_follow_car/line_follow_car.ino"

unsigned checks = 0;
void check(bool ok, const char* message) {
  ++checks;
  if (!ok) { std::cerr << "FAIL: " << message << '\n'; std::exit(1); }
}
bool stopped() { return !gpio[7] && !gpio[8] && !gpio[9] && !gpio[10]; }
void command(const char* text) { Serial.input = text; loop(); }
void sample(int left, int right) {
  gpio[4] = left; gpio[2] = right; loop(); // Physical LEFT D4, RIGHT D2.
  testMillis += FILTER_MS + 1; loop();
}
void boot() {
  testMillis = lastReport = 0;
  for (int& value : gpio) value = 0;
  for (Sensor& sensor : sensors) sensor = Sensor{};
  Serial.input.clear(); Serial.output.clear();
  gpio[4] = 0; gpio[2] = 1; // Each sensor has independently learned polarity.
  setup();
  check(stopped() && !following, "boot holds both wheels stopped");
  check(!calibrated(), "boot needs fresh calibration");
}
void calibrate() {
  sample(0, 1); command("w\n");
  check(sensors[0].white == 0 && sensors[1].white == 1, "w records actual white independently");
  check(stopped() && !following, "white sampling holds motors off");
  sample(1, 0); command("b\n");
  check(sensors[0].black == 1 && sensors[1].black == 0, "b records actual black independently");
  check(calibrated() && stopped(), "valid contrast ready with motors off");
}
void start() { sample(0, 1); command("f\n"); check(following, "local f starts with both heads on the white road"); }

int main() {
  boot(); command("f\n");
  check(!following && stopped(), "uncalibrated start refused");
  calibrate(); sample(1, 0); command("f\n");
  check(!following && stopped(), "start refused with both heads on black");
  start();
  check(gpio[7] == HIGH && gpio[8] == LOW && gpio[9] == HIGH && gpio[10] == LOW,
        "white/white drives both wheels forward");
  // One USB f sustains driving beyond all former heartbeat deadlines, with
  // neither a connected MSP nor valid packets on the old UART pins.
  for (unsigned n = 0; n < 1200; ++n) {
    testMillis += 10; gpio[5] = n & 1; gpio[6] = (n >> 1) & 1; loop();
    check(following && gpio[7] && !gpio[8] && gpio[9] && !gpio[10],
          "white-road drive continues independently of MSP/ESP UART activity");
  }
  command("s\n"); check(!following && stopped(), "local s stops sustained standalone drive");
  start();
  sample(1, 1);
  check(std::string(mode) == "TURN_RIGHT" && gpio[7] && !gpio[8] && !gpio[9] && !gpio[10],
        "physical left D4 black drives left wheel and stops right wheel to avoid left border");
  sample(0, 1);
  check(std::string(mode) == "FORWARD" && gpio[7] && gpio[9], "returning to white recentres forward");
  sample(0, 0);
  check(std::string(mode) == "TURN_LEFT" && !gpio[7] && !gpio[8] && gpio[9] && !gpio[10],
        "physical right D2 black stops left wheel and drives right wheel to avoid right border");
  sample(1, 0);
  check(!following && stopped() && std::string(mode) == "BOTH_BLACK", "both black latches stopped");
  sample(0, 1);
  check(!following && stopped(), "white after both black does not restart automatically");
  start(); command("fs\n");
  check(!following && stopped(), "stop beats start in the same serial batch");
  start(); command("w\n");
  check(!following && stopped(), "recalibration while following stops wheels");
  command("c\n");
  check(!calibrated() && stopped(), "clear invalidates both samples and stops");

  boot(); calibrate(); start(); sample(1, 1);
  const uint32_t cornerStarted=testMillis;
  testMillis=cornerStarted+750; loop();
  check(following && std::string(mode)=="TURN_RIGHT", "slow turn continues after old 750ms cutoff");
  testMillis=cornerStarted+TURN_LIMIT_MS-1; loop();
  check(following, "turn continues before configured deadline");
  testMillis=cornerStarted+TURN_LIMIT_MS; loop();
  check(!following && stopped() && std::string(mode) == "TURN_TIMEOUT", "prolonged correction times out");
  sample(0, 1);
  check(!following && stopped(), "turn timeout needs a new f after recentering");

  boot(); calibrate(); start();
  for (unsigned i = 0; i < 24; ++i) { testMillis += 7; gpio[4] = !gpio[4]; loop(); }
  check(!following && stopped() && std::string(mode) == "SIGNAL_FAULT", "unsettled input latches stopped");

  boot(); command("w\n"); command("b\n"); command("f\n");
  check(!calibrated() && !following && stopped(), "identical black/white outputs refuse movement");
  std::cout << "PASS: " << checks << " actual-sketch GPIO, calibration, serial and timeout assertions.\n";
}
'''
# The harness is in build/, so its include resolves the unchanged actual sketch.
test_source = project / "build" / "white_lane_sketch_tests.cpp"
test_source.write_text(harness, encoding="utf-8")
exe = build / "white_lane_sketch_tests.exe"
subprocess.run([
    r"C:\msys64\ucrt64\bin\g++.exe", "-std=c++11", "-Wall", "-Wextra", "-Werror", "-static",
    "-I", str(build), str(test_source), "-o", str(exe),
], check=True)
subprocess.run([str(exe)], check=True)
