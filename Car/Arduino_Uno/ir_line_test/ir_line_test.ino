#include <Arduino.h>

// IR sensor OUT pins.
const uint8_t SENSOR_COUNT = 2;
const uint8_t IR_PINS[SENSOR_COUNT] = {2, 4};

// Keep the existing L298N motor-control outputs stopped.
const uint8_t MOTOR_PINS[] = {7, 8, 9, 10};

const uint32_t DEBOUNCE_MS = 50;
const uint32_t REPORT_MS = 500;
const uint8_t CAL_SAMPLES = 40;

struct SensorState {
  int8_t whiteLevel = -1;
  int8_t blackLevel = -1;
  uint8_t raw = LOW;
  uint8_t candidate = LOW;
  uint8_t stable = LOW;
  bool settled = false;
  uint32_t candidateSince = 0;
};

SensorState sensors[SENSOR_COUNT];
uint32_t lastReportMs = 0;

bool calibrated(const SensorState& sensor) {
  return sensor.whiteLevel >= 0 &&
         sensor.blackLevel >= 0 &&
         sensor.whiteLevel != sensor.blackLevel;
}

void printHelp() {
  Serial.println(F("IR LINE TEST - D2 and D4"));
  Serial.println(F("Motors stopped."));
  Serial.println(F("w: place BOTH sensors over WHITE, then send w."));
  Serial.println(F("b: place BOTH sensors over BLACK, then send b."));
  Serial.println(F("c: clear calibration."));
  Serial.println(F("?: show instructions."));
  Serial.println(F("Repeat calibration after reset or power-off."));
}

void printReading() {
  bool anyBlack = false;

  for (uint8_t i = 0; i < SENSOR_COUNT; ++i) {
    if (i != 0) {
      Serial.print(F(" | "));
    }

    Serial.print(F("D"));
    Serial.print(IR_PINS[i]);
    Serial.print(F(" RAW="));
    Serial.print(sensors[i].raw);
    Serial.print(F(" "));

    if (!calibrated(sensors[i])) {
      Serial.print(F("NOT CALIBRATED"));
    } else if (!sensors[i].settled) {
      Serial.print(F("UNSTABLE"));
    } else if (sensors[i].stable == sensors[i].blackLevel) {
      Serial.print(F("OK - BLACK"));
      anyBlack = true;
    } else {
      Serial.print(F("WHITE"));
    }
  }

  Serial.println();
  digitalWrite(LED_BUILTIN, anyBlack ? HIGH : LOW);
}

void captureSurface(bool black) {
  digitalWrite(LED_BUILTIN, LOW);

  uint8_t highCounts[SENSOR_COUNT] = {0, 0};

  for (uint8_t i = 0; i < SENSOR_COUNT; ++i) {
    if (black) {
      sensors[i].blackLevel = -1;
    } else {
      sensors[i].whiteLevel = -1;
    }
  }

  Serial.println(
    black ? F("Sampling BLACK: hold still...")
          : F("Sampling WHITE: hold still...")
  );

  for (uint8_t sample = 0; sample < CAL_SAMPLES; ++sample) {
    for (uint8_t i = 0; i < SENSOR_COUNT; ++i) {
      if (digitalRead(IR_PINS[i]) == HIGH) {
        ++highCounts[i];
      }
    }

    delay(5);
  }

  for (uint8_t i = 0; i < SENSOR_COUNT; ++i) {
    Serial.print(F("D"));
    Serial.print(IR_PINS[i]);

    if (highCounts[i] > 2 &&
        highCounts[i] < CAL_SAMPLES - 2) {
      Serial.println(F(": UNSTABLE sample. Hold still and retry."));
    } else {
      const int8_t level =
        highCounts[i] >= CAL_SAMPLES - 2 ? HIGH : LOW;

      if (black) {
        sensors[i].blackLevel = level;
      } else {
        sensors[i].whiteLevel = level;
      }

      Serial.print(
        black ? F(": BLACK RAW=")
              : F(": WHITE RAW=")
      );
      Serial.println(level);

      if (sensors[i].whiteLevel >= 0 &&
          sensors[i].blackLevel >= 0) {
        if (calibrated(sensors[i])) {
          Serial.println(F("Calibration ready."));
        } else {
          Serial.println(
            F("NO CONTRAST: same reading on black and white.")
          );
          Serial.println(
            F("Check wiring, height and sensitivity; repeat w/b.")
          );
        }
      }
    }

    sensors[i].settled = false;
    sensors[i].candidate = digitalRead(IR_PINS[i]);
    sensors[i].candidateSince =
      static_cast<uint32_t>(millis());
  }
}

void setup() {
  for (uint8_t pin : MOTOR_PINS) {
    digitalWrite(pin, LOW);
    pinMode(pin, OUTPUT);
  }

  digitalWrite(LED_BUILTIN, LOW);
  pinMode(LED_BUILTIN, OUTPUT);

  for (uint8_t i = 0; i < SENSOR_COUNT; ++i) {
    // No internal 5V pull-up on the 3.3V sensor outputs.
    pinMode(IR_PINS[i], INPUT);

    sensors[i].raw = digitalRead(IR_PINS[i]);
    sensors[i].candidate = sensors[i].raw;
    sensors[i].candidateSince =
      static_cast<uint32_t>(millis());
  }

  Serial.begin(115200);
  printHelp();
  printReading();
}

void loop() {
  if (Serial.available() > 0) {
    const char command = static_cast<char>(Serial.read());

    if (command == 'w' || command == 'W') {
      captureSurface(false);
    } else if (command == 'b' || command == 'B') {
      captureSurface(true);
    } else if (command == 'c' || command == 'C') {
      for (uint8_t i = 0; i < SENSOR_COUNT; ++i) {
        sensors[i].whiteLevel = -1;
        sensors[i].blackLevel = -1;
      }

      digitalWrite(LED_BUILTIN, LOW);
      Serial.println(F("Calibration cleared. Repeat w and b."));
    } else if (command == '?' ||
               command == 'h' ||
               command == 'H') {
      printHelp();
    }
  }

  const uint32_t now = static_cast<uint32_t>(millis());
  bool changed = false;

  for (uint8_t i = 0; i < SENSOR_COUNT; ++i) {
    sensors[i].raw = digitalRead(IR_PINS[i]);

    if (sensors[i].raw != sensors[i].candidate) {
      sensors[i].candidate = sensors[i].raw;
      sensors[i].candidateSince = now;
      changed |= sensors[i].settled;
      sensors[i].settled = false;
    } else if (
      !sensors[i].settled &&
      static_cast<uint32_t>(
        now - sensors[i].candidateSince
      ) >= DEBOUNCE_MS
    ) {
      sensors[i].stable = sensors[i].candidate;
      sensors[i].settled = true;
      changed = true;
    }
  }

  if (changed ||
      static_cast<uint32_t>(now - lastReportMs) >= REPORT_MS) {
    lastReportMs = now;
    printReading();
  }
}