// Arduino Uno communication bench v1.0, 2026-10-29.
// AI-assisted project-team starter. This sketch never commands wheel motion.
// Future UART wiring: D5 RX, D6 TX, BOTH through a 3.3V/5V level converter.
// USB Serial Monitor: 115200. Inter-board SoftwareSerial: 9600, 8N1.
#include <Arduino.h>
#include <SoftwareSerial.h>
#include <string.h>

SoftwareSerial supervisor(5, 6); // receive, transmit
const uint8_t motorPins[] = {7, 8, 9, 10};
struct Line {
  char text[48];
  uint8_t used = 0;
  bool discard = false;
};
Line usbInput, supervisorInput;
bool indicatorOn = false;

void handleCommand(const char *command, Print &reply) {
  if (!strcmp(command, "PING")) {
    reply.println(F("PONG UNO"));
  } else if (!strcmp(command, "LED ON") || !strcmp(command, "LED OFF")) {
    indicatorOn = !strcmp(command, "LED ON");
    digitalWrite(LED_BUILTIN, indicatorOn ? HIGH : LOW);
    reply.println(indicatorOn ? F("ACK LED ON") : F("ACK LED OFF"));
  } else if (!strcmp(command, "STATUS")) {
    reply.println(indicatorOn ? F("STATUS LED=ON MOTORS=DISABLED")
                              : F("STATUS LED=OFF MOTORS=DISABLED"));
  } else if (!strcmp(command, "HELP") || !strcmp(command, "?")) {
    reply.println(F("PING | STATUS | LED ON | LED OFF; bench only"));
  } else {
    reply.println(F("ERR UNKNOWN COMMAND"));
  }
}

void receive(Stream &input, Print &reply, Line &line) {
  uint8_t budget = 64;
  while (budget-- && input.available()) {
    int value = input.read();
    if (value < 0) break;
    char c = static_cast<char>(value);
    if (c == '\r' || c == '\n') {
      if (line.discard) reply.println(F("ERR INVALID LINE"));
      else if (line.used) {
        line.text[line.used] = '\0';
        handleCommand(line.text, reply);
      }
      line.used = 0;
      line.discard = false;
    } else if (!line.discard) {
      if (value < 32 || value > 126 || line.used >= sizeof(line.text) - 1) {
        line.used = 0;
        line.discard = true;
      } else {
        if (c >= 'a' && c <= 'z') c -= 'a' - 'A';
        line.text[line.used++] = c;
      }
    }
  }
}

void setup() {
  for (uint8_t pin : motorPins) {
    digitalWrite(pin, LOW);
    pinMode(pin, OUTPUT);
  }
  digitalWrite(LED_BUILTIN, LOW);
  pinMode(LED_BUILTIN, OUTPUT);
  Serial.begin(115200);
  supervisor.begin(9600);
  Serial.println(F("UNO UART BENCH v1.0: D5 RX / D6 TX; motors disabled"));
}

void loop() {
  if (supervisor.overflow()) {
    supervisorInput.used = 0;
    supervisorInput.discard = true;
  }
  receive(supervisor, supervisor, supervisorInput);
  receive(Serial, Serial, usbInput);
}
