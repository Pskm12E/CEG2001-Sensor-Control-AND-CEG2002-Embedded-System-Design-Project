// Minimal host-only Arduino API for testing the actual sketch without motors.
#pragma once
#include <cassert>
#include <cstdint>
#include <deque>
#include <string>

#define HIGH 1
#define LOW 0
#define OUTPUT 1
#define F(text) text

inline uint32_t fakeMillis = 0;
inline int pinLevels[20] = {};
inline int pinModes[20] = {};
inline unsigned long millis() { return fakeMillis; }
inline void digitalWrite(uint8_t pin, int level) { pinLevels[pin] = level; }
inline void pinMode(uint8_t pin, int mode) { pinModes[pin] = mode; }

struct FakeSerial {
  std::deque<char> input;
  unsigned long baud = 0;
  void begin(unsigned long value) { baud = value; }
  int available() { return static_cast<int>(input.size()); }
  int read() {
    if (input.empty()) return -1;
    const char value = input.front();
    input.pop_front();
    return value;
  }
  void println(const char*) {}
  void send(const std::string& text) {
    for (char value : text) input.push_back(value);
  }
};
inline FakeSerial Serial;
