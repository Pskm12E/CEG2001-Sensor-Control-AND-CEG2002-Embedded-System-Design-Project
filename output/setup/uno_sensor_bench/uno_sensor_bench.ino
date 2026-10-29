/*
 * USB-only sensor checks for an Arduino Uno R3.
 * This is a diagnostic sketch, NOT final robot-control firmware.
 * No motor, pump, battery or other microcontroller connects to this test.
 * Choose ONE mode, wire with USB unplugged, then upload.
 * Serial Monitor: 115200 baud.
 *
 * MODE 0: heartbeat only (default, no sensors required)
 * MODE 1: soil module AO -> A0; GND -> GND;
 *         VCC -> 5V ONLY for a module rated to run at 5V.
 * MODE 2: IR left OUT -> D2, right OUT -> D3;
 *         GND -> GND; VCC -> 5V for 5V-rated modules.
 * MODE 3: standard 5V HC-SR04 VCC -> 5V; GND -> GND;
 *         TRIG -> D4; ECHO -> D5 (direct only on this 5V Uno).
 *         Pico wiring needs the divider shown in the guide.
 */
#include <Arduino.h>

const uint8_t TEST_MODE = 0;  // Change to 1, 2 or 3 for each sensor test.
const uint8_t IR_LEFT = 2;
const uint8_t IR_RIGHT = 3;
const uint8_t TRIG = 4;
const uint8_t ECHO = 5;

void setup() {
  Serial.begin(115200);
  pinMode(LED_BUILTIN, OUTPUT);
  if (TEST_MODE == 2) {
    pinMode(IR_LEFT, INPUT);  // Do not enable 5V internal pull-ups.
    pinMode(IR_RIGHT, INPUT);
  }
  if (TEST_MODE == 3) {
    digitalWrite(TRIG, LOW);
    pinMode(TRIG, OUTPUT);
    pinMode(ECHO, INPUT);
  }
  Serial.println(F("USB SENSOR BENCH - no actuators connected"));
  Serial.print(F("mode="));
  Serial.println(TEST_MODE);
}

void loop() {
  static bool led = false;
  led = !led;
  digitalWrite(LED_BUILTIN, led ? HIGH : LOW);
  Serial.print(F("ms="));
  Serial.print(millis());

  switch (TEST_MODE) {
    case 0:
      Serial.println(F(",heartbeat=OK"));
      break;
    case 1: {
      // Average a few readings; retain raw ADC counts, not invented percent.
      unsigned long total = 0;
      for (uint8_t n = 0; n < 16; ++n) {
        total += analogRead(A0);
        delay(2);
      }
      Serial.print(F(",soil_adc="));
      Serial.println(total / 16.0f, 1);
      break;
    }
    case 2:
      Serial.print(F(",ir_left="));
      Serial.print(digitalRead(IR_LEFT));
      Serial.print(F(",ir_right="));
      Serial.println(digitalRead(IR_RIGHT));
      break;
    case 3: {
      digitalWrite(TRIG, LOW);
      delayMicroseconds(2);
      digitalWrite(TRIG, HIGH);
      delayMicroseconds(10);
      digitalWrite(TRIG, LOW);
      const unsigned long echo_us = pulseIn(ECHO, HIGH, 30000UL);
      if (echo_us == 0) {
        // A missing echo is unknown, never proof of an unobstructed path.
        Serial.println(F(",distance=NO_ECHO"));
      } else {
        Serial.print(F(",echo_us="));
        Serial.print(echo_us);
        Serial.print(F(",distance_cm="));
        Serial.println(echo_us / 58.0f, 1);
      }
      break;
    }
    default:
      Serial.println(F(",error=INVALID_MODE"));
      break;
  }
  delay(250);  // Bench only; final robot needs non-blocking timers/ISRs.
}
