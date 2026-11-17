#include <Arduino.h>
#include <string.h>

// Sensor-only test: LEFT S -> A0, RIGHT S -> A1.
// VCC -> 3.3V, GND -> common GND. Keep the motor battery OFF.
const uint8_t IR_PINS[2] = {A0, A1};
const uint16_t MIN_CONTRAST = 40;
const uint16_t MAX_SPREAD = 30;
const int HYSTERESIS = 8;
// Software detection sensitivity only. 50 = midpoint; 70 detects black
// after 30% of the measured change from white towards black.
// Keep a margin at both ends for the existing 8-count hysteresis.
const uint8_t MIN_SENSITIVITY = 25, MAX_SENSITIVITY = 75;
uint8_t sensitivity = 70;

int whiteValue[2] = {-1, -1};
int blackValue[2] = {-1, -1};
bool known[2] = {false, false};
bool blackNow[2] = {false, false};
bool whiteAttempted[2] = {false, false};
bool blackAttempted[2] = {false, false};
uint32_t lastReport = 0;
char commandLine[16];
uint8_t commandUsed = 0;
bool commandTooLong = false;

int readIR(uint8_t i) {
  unsigned int total = 0;
  for (uint8_t n = 0; n < 4; ++n) total += analogRead(IR_PINS[i]);
  return total / 4;
}

bool calibrated(uint8_t i) {
  return whiteValue[i] >= 0 && blackValue[i] >= 0 &&
         abs(blackValue[i] - whiteValue[i]) >= MIN_CONTRAST;
}

int thresholdFor(uint8_t i) {
  // Use 32-bit arithmetic: the product can exceed an Uno's 16-bit int.
  const long span = long(blackValue[i]) - whiteValue[i];
  return whiteValue[i] + int(span * (100 - sensitivity) / 100);
}

void printSensitivity() {
  Serial.print(F("SENSITIVITY=")); Serial.print(sensitivity);
  Serial.println(F(" (25..75; higher detects black sooner; 50 = midpoint)"));
  Serial.println(F("Changes software threshold, not RAW or sensor-module LEDs."));
  if (!calibrated(0) || !calibrated(1))
    Serial.println(F("Capture valid w and b first; sensitivity cannot replace missing samples."));
}

void setSensitivity(uint8_t value) {
  sensitivity = value;
  known[0] = known[1] = false; // Reclassify with the new threshold.
  printSensitivity();
}

void printOne(uint8_t i) {
  const int raw = readIR(i);
  Serial.print(i == 0 ? F("LEFT A0: ") : F("RIGHT A1: "));
  Serial.print(F("RAW=")); Serial.print(raw);
  Serial.print(F(" W=")); Serial.print(whiteValue[i]);
  Serial.print(F(" B=")); Serial.print(blackValue[i]);

  if (!calibrated(i)) {
    known[i] = false;
    if (whiteValue[i] < 0 || blackValue[i] < 0) {
      if (whiteValue[i] < 0)
        Serial.print(whiteAttempted[i] ? F(" WHITE_NOISY") : F(" NEED_w"));
      if (blackValue[i] < 0)
        Serial.print(blackAttempted[i] ? F(" BLACK_NOISY") : F(" NEED_b"));
      Serial.println(F(""));
    } else {
      Serial.print(F(" LOW_CONTRAST GAP="));
      Serial.print(abs(blackValue[i] - whiteValue[i]));
      Serial.print(F(" NEED>=")); Serial.println(MIN_CONTRAST);
    }
    return;
  }

  const int threshold = thresholdFor(i);
  if (raw >= threshold + HYSTERESIS) {
    blackNow[i] = blackValue[i] > whiteValue[i];
    known[i] = true;
  } else if (raw <= threshold - HYSTERESIS) {
    blackNow[i] = blackValue[i] < whiteValue[i];
    known[i] = true;
  }
  Serial.print(F(" T=")); Serial.print(threshold);
  Serial.print(F(" SENS=")); Serial.print(sensitivity);
  Serial.print(F(" OK "));
  Serial.println(!known[i] ? F("UNCERTAIN") :
                 blackNow[i] ? F("BLACK") : F("WHITE"));
}

void report() {
  printOne(0);
  printOne(1);
  Serial.println(calibrated(0) && calibrated(1)
    ? F("CAL=1: BOTH SENSORS HAVE CONTRAST")
    : F("CAL=0: CALIBRATION INCOMPLETE"));
  digitalWrite(LED_BUILTIN,
    (known[0] && blackNow[0]) || (known[1] && blackNow[1]));
}

void capture(bool black) {
  unsigned long sum[2] = {0, 0};
  int low[2] = {1023, 1023}, high[2] = {0, 0};
  known[0] = known[1] = false;
  digitalWrite(LED_BUILTIN, LOW);
  for (uint8_t i = 0; i < 2; ++i) {
    if (black) blackValue[i] = -1;
    else whiteValue[i] = -1;
  }
  Serial.println(black ? F("b/black received: sampling BLACK at fixed height")
                       : F("w/white received: sampling WHITE at fixed height"));
  for (uint8_t n = 0; n < 40; ++n) {
    for (uint8_t i = 0; i < 2; ++i) {
      const int value = readIR(i);
      sum[i] += value;
      if (value < low[i]) low[i] = value;
      if (value > high[i]) high[i] = value;
    }
    delay(5); // Sensor-only capture; no driving code runs here.
  }
  for (uint8_t i = 0; i < 2; ++i) {
    const int mean = int((sum[i] + 20) / 40);
    const int spread = high[i] - low[i];
    const int saved = spread <= MAX_SPREAD ? mean : -1;
    if (black) { blackValue[i] = saved; blackAttempted[i] = true; }
    else { whiteValue[i] = saved; whiteAttempted[i] = true; }
    Serial.print(black ? F("CAPTURE BLACK ") : F("CAPTURE WHITE "));
    Serial.print(i == 0 ? F("LEFT A0") : F("RIGHT A1"));
    Serial.print(F(" MEAN=")); Serial.print(mean);
    Serial.print(F(" MIN=")); Serial.print(low[i]);
    Serial.print(F(" MAX=")); Serial.print(high[i]);
    Serial.print(F(" SPREAD=")); Serial.print(spread);
    Serial.println(saved >= 0 ? F(" SAVED") : F(" REJECTED_NOISE (limit 30)"));
  }
  report();
}

void setup() {
  // Hold the existing L298N direction inputs LOW; no motion commands exist.
  for (uint8_t pin = 7; pin <= 10; ++pin) {
    digitalWrite(pin, LOW);
    pinMode(pin, OUTPUT);
  }
  pinMode(A0, INPUT);
  pinMode(A1, INPUT);
  pinMode(LED_BUILTIN, OUTPUT);
  digitalWrite(LED_BUILTIN, LOW);
  Serial.begin(115200);
  Serial.println(F("ANALOG IR CALIBRATION V3: LEFT A0, RIGHT A1"));
  Serial.println(F("New Line: w/white = WHITE; b/black = BLACK; c/clear = reset"));
  Serial.println(F("sense 70 = sensitivity; + increases by 5; - decreases by 5; status = readings"));
  Serial.println(F("Keep the SAME height for both colours. Motors OFF."));
  printSensitivity();
}

void processCommand() {
  commandLine[commandUsed] = 0;
  // Whole commands only: the letter c inside "black" must never clear samples.
  if (commandTooLong) {
    Serial.println(F("Command too long: use w, b, c, sense 70, +, -, or status, then Enter."));
    return;
  }
  char* text = commandLine;
  while (*text == ' ') ++text;
  size_t length = strlen(text);
  while (length && text[length - 1] == ' ') text[--length] = 0;
  if (!strcmp(text, "w") || !strcmp(text, "white")) capture(false);
  else if (!strcmp(text, "b") || !strcmp(text, "black")) capture(true);
  else if (!strcmp(text, "c") || !strcmp(text, "clear")) {
    for (uint8_t i = 0; i < 2; ++i) {
      whiteValue[i] = blackValue[i] = -1;
      whiteAttempted[i] = blackAttempted[i] = known[i] = false;
    }
    Serial.println(F("Calibration explicitly cleared."));
    report();
  } else if (!strcmp(text, "sense") || !strcmp(text, "status") || !strcmp(text, "?")) {
    printSensitivity();
    report();
  } else if (!strcmp(text, "+") || !strcmp(text, "-")) {
    int value = sensitivity + (*text == '+' ? 5 : -5);
    if (value < MIN_SENSITIVITY) value = MIN_SENSITIVITY;
    if (value > MAX_SENSITIVITY) value = MAX_SENSITIVITY;
    setSensitivity(uint8_t(value));
    report();
  } else if (!strncmp(text, "sense ", 6)) {
    // Require a complete two-digit value, never silently parse partial text.
    if (strlen(text + 6) != 2 || text[6] < '0' || text[6] > '9' ||
        text[7] < '0' || text[7] > '9') {
      Serial.println(F("Use sense 25 through sense 75 (example: sense 70)."));
      return;
    }
    const uint8_t value = (text[6] - '0') * 10 + (text[7] - '0');
    if (value < MIN_SENSITIVITY || value > MAX_SENSITIVITY) {
      Serial.println(F("Sensitivity must be 25..75; setting unchanged."));
      return;
    }
    setSensitivity(value);
    report();
  } else if (*text) Serial.println(F("Unknown command: use w, b, c, sense 70, +, -, status."));
}

void loop() {
  while (Serial.available()) {
    char c = Serial.read();
    if (c == '\n' || c == '\r') {
      processCommand();
      commandUsed = 0;
      commandTooLong = false;
    } else if (c < 32 || c > 126 || commandUsed >= sizeof(commandLine) - 1) {
      commandTooLong = true;
    } else if (!commandTooLong) {
      if (c >= 'A' && c <= 'Z') c += 'a' - 'A';
      commandLine[commandUsed++] = c;
    }
  }
  if (uint32_t(millis() - lastReport) >= 500) {
    lastReport = millis();
    report();
  }
}
