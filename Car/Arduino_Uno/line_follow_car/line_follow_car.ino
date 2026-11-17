#include <Arduino.h>
#include <stdio.h>

// Looking forward from behind the car: D4 = LEFT IR, D2 = RIGHT IR.
// Both IR VCC -> Uno 5V; common GND. No INPUT_PULLUP.
// L298N: D7 IN1, D8 IN2, D9 IN3, D10 IN4; ENA/ENB jumpers fitted.
// Follow the WHITE road inside BLACK borders. Both heads see white when centred.
// One head sees black: steer AWAY from that border.
// Arduino-only: no MSP/ESP UART, approval, heartbeat or ultrasonic dependency.
// Calibrate actual WHITE with w and actual BLACK with b; do not swap them.
const uint8_t IR_PINS[2] = {4, 2};
const uint8_t MOTOR_PINS[4] = {7, 8, 9, 10};
const bool LEFT_FORWARD_IN1_HIGH = true;
const bool RIGHT_FORWARD_IN3_HIGH = true;
// OUT1/2 = left wheel; OUT3/4 = right wheel. Do not exchange turn outputs:
// left black -> left wheel forward/right stopped -> steer right (and vice versa).
const bool REVERSE_TURN_OUTPUTS = false;
const uint32_t FILTER_MS = 8;
const uint32_t TURN_LIMIT_MS = 3000; // Slow-corner allowance; no endless stall.
const uint32_t UNSTABLE_LIMIT_MS = 150;
const uint32_t REPORT_MS = 500;

// BEGIN CONTROL LOGIC
enum Action : uint8_t { STOP, FORWARD, TURN_LEFT, TURN_RIGHT };
constexpr bool contrast(int8_t white, int8_t black) {
  return white >= 0 && black >= 0 && white != black;
}
constexpr bool blackReading(uint8_t value, int8_t white, int8_t black) {
  return contrast(white, black) && value == black;
}
constexpr bool whiteReading(uint8_t value, int8_t white, int8_t black) {
  return contrast(white, black) && value == white;
}
constexpr Action steerFor(bool leftBlack, bool rightBlack) {
  return leftBlack ? (rightBlack ? STOP : TURN_RIGHT)
                   : (rightBlack ? TURN_LEFT : FORWARD);
}
constexpr Action motorOutputFor(Action action, bool reverseTurns) {
  return !reverseTurns ? action
         : action == TURN_LEFT ? TURN_RIGHT
         : action == TURN_RIGHT ? TURN_LEFT : action;
}
constexpr bool expired(uint32_t now, uint32_t start, uint32_t limit) {
  return static_cast<uint32_t>(now - start) >= limit;
}
constexpr bool leftWheelOn(Action action) {
  return action == FORWARD || action == TURN_RIGHT;
}
constexpr bool rightWheelOn(Action action) {
  return action == FORWARD || action == TURN_LEFT;
}
// END CONTROL LOGIC

struct Sensor {
  int8_t white = -1, black = -1;
  uint8_t raw = LOW, candidate = LOW, stable = LOW;
  uint32_t since = 0;
  bool settled = false;
};
Sensor sensors[2];
bool following = false, turning = false, uncertain = false;
uint32_t turnSince = 0, uncertainSince = 0, lastReport = 0;
const char* mode = "STOP";

void drive(Action action) {
  const Action output = motorOutputFor(action, REVERSE_TURN_OUTPUTS);
  const bool channelAOn = leftWheelOn(output);
  const bool channelBOn = rightWheelOn(output);
  digitalWrite(7, channelAOn && LEFT_FORWARD_IN1_HIGH ? HIGH : LOW);
  digitalWrite(8, channelAOn && !LEFT_FORWARD_IN1_HIGH ? HIGH : LOW);
  digitalWrite(9, channelBOn && RIGHT_FORWARD_IN3_HIGH ? HIGH : LOW);
  digitalWrite(10, channelBOn && !RIGHT_FORWARD_IN3_HIGH ? HIGH : LOW);
}

void stopFollowing(const char* reason) {
  drive(STOP);
  following = false;
  turning = uncertain = false;
  mode = reason;
}

bool calibrated() {
  return contrast(sensors[0].white, sensors[0].black) &&
         contrast(sensors[1].white, sensors[1].black);
}

bool blackAt(uint8_t index) {
  return blackReading(sensors[index].stable,
                      sensors[index].white, sensors[index].black);
}

bool whiteAt(uint8_t index) {
  return whiteReading(sensors[index].stable,
                      sensors[index].white, sensors[index].black);
}

void readSensors(uint32_t now) {
  for (uint8_t i = 0; i < 2; ++i) {
    Sensor& s = sensors[i];
    s.raw = digitalRead(IR_PINS[i]);
    if (s.raw != s.candidate) {
      s.candidate = s.raw;
      s.since = now;
      s.settled = false;
    } else if (!s.settled && expired(now, s.since, FILTER_MS)) {
      s.stable = s.candidate;
      s.settled = true;
    }
  }
}

void help() {
  Serial.println(F("UNO WHITE-ROAD STANDALONE: LEFT D4, RIGHT D2; Serial 115200."));
  Serial.println(F("Arduino-only driving; MSP/ESP/ultrasonic do not control this sketch."));
  Serial.println(F("w: BOTH sensors over white; b: BOTH over black."));
  Serial.println(F("f: start following; s: stop; c: clear calibration."));
  Serial.println(F("WHITE road inside BLACK borders; BOTH see WHITE before f. ?: help."));
  Serial.println(F("Left black: turn RIGHT. Right black: turn LEFT."));
  Serial.println(REVERSE_TURN_OUTPUTS ? F("Turn motor outputs: REVERSED for corner test.")
                                    : F("Turn motor outputs: STANDARD."));
  Serial.println(F("BOTH black: stop; reposition on white and send f again."));
  Serial.println(F("Motor drive is full-on with the existing ENA/ENB jumpers."));
  Serial.print(F("Corner turn limit (ms): ")); Serial.println(TURN_LIMIT_MS);
}

void capture(bool black) {
  stopFollowing("CALIBRATING");
  uint8_t highs[2] = {0, 0};
  for (uint8_t i = 0; i < 2; ++i) {
    if (black) sensors[i].black = -1;
    else sensors[i].white = -1;
  }
  Serial.println(black ? F("Sampling BLACK; hold still...")
                       : F("Sampling WHITE; hold still..."));
  for (uint8_t n = 0; n < 40; ++n) {
    for (uint8_t i = 0; i < 2; ++i) {
      if (digitalRead(IR_PINS[i]) == HIGH) ++highs[i];
    }
    delay(5);  // Calibration only: motors are already stopped.
  }
  for (uint8_t i = 0; i < 2; ++i) {
    Serial.print(i == 0 ? F("LEFT D4: ") : F("RIGHT D2: "));
    if (highs[i] > 2 && highs[i] < 38) {
      Serial.println(F("unstable; hold still and retry."));
    } else {
      const int8_t value = highs[i] >= 38 ? HIGH : LOW;
      if (black) sensors[i].black = value;
      else sensors[i].white = value;
      Serial.print(black ? F("BLACK=") : F("WHITE="));
      Serial.println(value);
      if (sensors[i].white >= 0 && sensors[i].black >= 0) {
        Serial.println(contrast(sensors[i].white, sensors[i].black)
          ? F("Calibration OK.") : F("NO CONTRAST; check sensor/height/adjustment."));
      }
    }
    sensors[i].settled = false;
    sensors[i].candidate = digitalRead(IR_PINS[i]);
    sensors[i].since = static_cast<uint32_t>(millis());
  }
  mode = "STOP";
}

void commands() {
  bool stop = false, white = false, black = false;
  bool clear = false, start = false, info = false;
  const int pending = Serial.available();
  for (int n = 0; n < pending; ++n) {
    const int c = Serial.read();
    stop |= c == 's' || c == 'S';
    white |= c == 'w' || c == 'W';
    black |= c == 'b' || c == 'B';
    clear |= c == 'c' || c == 'C';
    start |= c == 'f' || c == 'F';
    info |= c == '?' || c == 'h' || c == 'H';
  }
  // Stop takes priority over all other commands in the same input batch.
  if (stop) {
    stopFollowing("STOP");
    Serial.println(F("STOPPED."));
  } else if (clear) {
    stopFollowing("STOP");
    for (uint8_t i = 0; i < 2; ++i) sensors[i].white = sensors[i].black = -1;
    Serial.println(F("Calibration cleared. Repeat w and b."));
  } else if (white || black) {
    capture(!white);
  } else if (start && !following) {
    if (!calibrated()) Serial.println(F("START REFUSED: calibrate BOTH sensors with w/b."));
    else if (!sensors[0].settled || !sensors[1].settled || !whiteAt(0) || !whiteAt(1))
      Serial.println(F("START REFUSED: centre on the road; BOTH must see WHITE."));
    else {
      // Print before starting motion. Repeated f does not restart recovery timers.
      Serial.println(F("FOLLOWING WHITE road. Send s to stop."));
      following = true;
      turning = uncertain = false;
      mode = "FORWARD";
    }
  } else if (info) {
    stopFollowing("STOP");
    help();
  }
}

void follow(uint32_t now) {
  if (!following) return;
  if (!calibrated()) { stopFollowing("UNCALIBRATED"); return; }
  if (!sensors[0].settled || !sensors[1].settled) {
    drive(STOP);
    mode = "WAIT_SIGNAL";
    if (!uncertain) { uncertain = true; uncertainSince = now; }
    if (expired(now, uncertainSince, UNSTABLE_LIMIT_MS)) stopFollowing("SIGNAL_FAULT");
    return;
  }
  uncertain = false;
  const Action action = steerFor(blackAt(0), blackAt(1));
  if (action == FORWARD) {
    turning = false;
    mode = "FORWARD";
    drive(FORWARD);
  } else if (action == TURN_LEFT || action == TURN_RIGHT) {
    if (!turning) { turning = true; turnSince = now; }
    if (expired(now, turnSince, TURN_LIMIT_MS)) { stopFollowing("TURN_TIMEOUT"); return; }
    mode = action == TURN_LEFT ? "TURN_LEFT" : "TURN_RIGHT";
    drive(action);
  } else {
    // Both black may be a cross-strip, blocked lane or an unknown position.
    // Latch stopped instead of choosing an arbitrary direction or driving on.
    stopFollowing("BOTH_BLACK");
  }
}

const char* sensorLabel(uint8_t i) {
  if (!contrast(sensors[i].white, sensors[i].black)) return "NC";
  if (!sensors[i].settled) return "?";
  return blackAt(i) ? "BLACK" : "WHITE";
}

void report(uint32_t now) {
  if (!expired(now, lastReport, REPORT_MS)) return;
  lastReport = now;
  char line[64];
  const int size = snprintf(line, sizeof(line), "L4=%s R2=%s MODE=%s\n",
                            sensorLabel(0), sensorLabel(1), mode);
  // Never wait for serial-buffer space while steering.
  if (size > 0 && size < static_cast<int>(sizeof(line)) && Serial.availableForWrite() >= size)
    Serial.write(reinterpret_cast<const uint8_t*>(line), size);
}

void setup() {
  for (uint8_t pin : MOTOR_PINS) { digitalWrite(pin, LOW); pinMode(pin, OUTPUT); }
  stopFollowing("STOP");
  for (uint8_t i = 0; i < 2; ++i) {
    pinMode(IR_PINS[i], INPUT);
    sensors[i].candidate = digitalRead(IR_PINS[i]);
    sensors[i].since = static_cast<uint32_t>(millis());
  }
  Serial.begin(115200);
  help();
}

void loop() {
  readSensors(static_cast<uint32_t>(millis()));
  commands();
  const uint32_t now = static_cast<uint32_t>(millis());
  follow(now);
  report(now);
}
