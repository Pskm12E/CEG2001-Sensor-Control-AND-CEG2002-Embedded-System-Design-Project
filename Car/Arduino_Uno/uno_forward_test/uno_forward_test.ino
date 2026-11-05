#include <Arduino.h>

// Arduino Uno -> L298N: D7 IN1, D8 IN2, D9 IN3, D10 IN4.
// This four-wire test requires ENA and ENB held HIGH by their jumper caps.
// The separate 5V-EN regulator jumper is NOT an enable jumper.
// USB powers the Uno; a suitable separate supply powers the motor driver.
// All grounds must be connected. There is no PWM speed control in this test.
const uint8_t LEFT_IN1 = 7;
const uint8_t LEFT_IN2 = 8;
const uint8_t RIGHT_IN3 = 9;
const uint8_t RIGHT_IN4 = 10;

// Physical forward depends on the motor leads and mounting.
// With power disconnected, swap a backwards motor's two output wires,
// OR change only that motor's constant below and upload again.
const bool LEFT_FORWARD_IN1_HIGH = true;
const bool RIGHT_FORWARD_IN3_HIGH = true;

bool driving = false;

void stopMotors() {
  // Equal inputs brake each motor while its enable jumper is fitted.
  digitalWrite(LEFT_IN1, LOW);
  digitalWrite(LEFT_IN2, LOW);
  digitalWrite(RIGHT_IN3, LOW);
  digitalWrite(RIGHT_IN4, LOW);
  driving = false;
}

void startForward() {
  // Print before energising the motors, never repeatedly while driving.
  Serial.println(F("FORWARD: continuous full drive. Send s to stop."));
  driving = true;
  digitalWrite(LEFT_IN1, LEFT_FORWARD_IN1_HIGH ? HIGH : LOW);
  digitalWrite(LEFT_IN2, LEFT_FORWARD_IN1_HIGH ? LOW : HIGH);
  digitalWrite(RIGHT_IN3, RIGHT_FORWARD_IN3_HIGH ? HIGH : LOW);
  digitalWrite(RIGHT_IN4, RIGHT_FORWARD_IN3_HIGH ? LOW : HIGH);
}

void setup() {
  // Set output latches LOW before changing the pins to outputs.
  const uint8_t pins[] = {LEFT_IN1, LEFT_IN2, RIGHT_IN3, RIGHT_IN4};
  for (uint8_t pin : pins) {
    digitalWrite(pin, LOW);
    pinMode(pin, OUTPUT);
  }
  stopMotors();
  Serial.begin(115200);
  Serial.println(F("UNO L298N CONTINUOUS TEST - D7/D8/D9/D10"));
  Serial.println(F("READY: stopped. Send f to run; s to stop. No auto-stop."));
}

void loop() {
  const int pending = Serial.available();
  if (pending <= 0) {
    return;
  }

  // Read the current input batch. A stop takes priority even if an f is queued.
  // Bound the read to this snapshot so incoming traffic cannot stall the loop.
  bool requestForward = false;
  bool requestStop = false;
  for (int i = 0; i < pending; ++i) {
    const int command = Serial.read();
    if (command == 's' || command == 'S') {
      requestStop = true;
    } else if (command == 'f' || command == 'F') {
      requestForward = true;
    }
  }

  if (requestStop) {
    stopMotors();
    Serial.println(F("STOPPED: stop command received."));
  } else if (requestForward && !driving) {
    startForward();
  }
  // No time limit: s/S commands stop; setup starts stopped after a reset.
  // Newlines, other characters and repeated f while driving do nothing.
}
