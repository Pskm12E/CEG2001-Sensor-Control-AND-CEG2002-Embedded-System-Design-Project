#include <Arduino.h>
#include <iostream>
#include "../uno_forward_test/uno_forward_test.ino"

void assertStopped() {
  assert(!driving);
  for (int pin = 7; pin <= 10; ++pin) assert(pinLevels[pin] == LOW);
}

void assertForward() {
  assert(driving);
  assert(pinLevels[7] == HIGH && pinLevels[8] == LOW);
  assert(pinLevels[9] == HIGH && pinLevels[10] == LOW);
}

int main() {
  setup();
  assertStopped();
  assert(Serial.baud == 115200);
  for (int pin = 7; pin <= 10; ++pin) assert(pinModes[pin] == OUTPUT);

  Serial.send("rbl?\r\n");
  while (Serial.available()) loop();
  assertStopped();

  fakeMillis = 100;
  Serial.send("f\r\n");
  loop();
  assertForward();
  assert(Serial.available() == 0);
  fakeMillis = 1100;
  Serial.send("f");
  loop();
  assertForward();
  fakeMillis = 600100;
  Serial.send("fff");
  loop();
  assertForward();
  assert(Serial.available() == 0);
  loop();
  assertForward();

  for (char stop : {'s', 'S'}) {
    Serial.send("F");
    loop();
    assertForward();
    ++fakeMillis;
    Serial.send(std::string(1, stop) + "f");
    loop();
    assertStopped();
    assert(Serial.available() == 0);
  }

  // Neither elapsed time nor millis rollover should stop continuous motion.
  fakeMillis = UINT32_MAX - 499;
  Serial.send("f");
  loop();
  assertForward();
  fakeMillis = 499;
  loop();
  assertForward();
  fakeMillis = 500;
  loop();
  assertForward();

  // Stop wins over forward anywhere in the same queued input batch.
  for (const char* commands : {"fs", "sf", "fSf", "S\r\nf"}) {
    Serial.send(commands);
    loop();
    assertStopped();
    assert(Serial.available() == 0);
    Serial.send("f");
    loop();
    assertForward();
  }

  // A fresh setup always requests stopped outputs.
  Serial.send("f");
  loop();
  assertForward();
  setup();
  assertStopped();
  std::cout << "PASS: startup, pin mapping, continuous motion, repeated commands, "
               "stop priority, rollover, reset.\n";
}
