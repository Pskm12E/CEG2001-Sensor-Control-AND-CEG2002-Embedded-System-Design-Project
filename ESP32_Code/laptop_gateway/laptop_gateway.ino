#include <Arduino.h>
#include <WiFi.h>
#include <RobotBench.h>
#include <NetworkConfig.h>

// Original DFRobot FireBeetle ESP32 (DFR0478), not FireBeetle 2 ESP32-E.
// USB console -> private Wi-Fi -> Pico onboard LED diagnostics only.
WiFiServer server(bench::PORT);
WiFiClient peer;
bench::Line<128> usbLine;
bench::Line<192> netLine;
bool apReady = false, active = false, ready = false, heartbeat = false;
uint32_t connectedAt = 0, lastReply = 0, sentAt = 0, nextId = 0, pending = 0;
char expected[16] = {};

void dropPeer(const char *reason) {
    if (active) {
        Serial.print("LINK DOWN: "); Serial.println(reason);
        if (pending && !heartbeat) Serial.println("ERROR request interrupted; not replayed");
    }
    peer.stop();
    active = ready = false;
    pending = 0;
    netLine.reset();
}

bool sendLine(const char *line) {
    char buffer[192];
    const int n = snprintf(buffer, sizeof(buffer), "%s\n", line);
    return n > 0 && n < static_cast<int>(sizeof(buffer)) &&
           peer.write(reinterpret_cast<const uint8_t *>(buffer), n) == static_cast<size_t>(n);
}

void printStatus() {
    Serial.print("STATUS BOARD=ESP32_FIREBEETLE ROLE=LAPTOP_GATEWAY AP=");
    Serial.print(apReady ? "READY" : "FAILED");
    Serial.print(" PICO_LINK=");
    Serial.print(ready ? "UP" : active ? "HANDSHAKE" : "DOWN");
    Serial.println(" MSP_LINK=NOT_CONNECTED BENCH_ONLY");
}

void request(const char *command, bool internal = false) {
    if (!bench::allowed(command)) { Serial.println("ERROR unsupported robot command"); return; }
    if (!ready) { if (!internal) Serial.println("ERROR Pico is not connected"); return; }
    if (pending) { if (!internal) Serial.println("BUSY wait for reply, then try again"); return; }
    if (++nextId == 0) { dropPeer("request ID exhausted"); return; }
    char message[64];
    snprintf(message, sizeof(message), "REQ %lu %s", static_cast<unsigned long>(nextId), command);
    pending = nextId;
    heartbeat = internal;
    sentAt = millis();
    snprintf(expected, sizeof(expected), "%s", command);
    if (!sendLine(message)) dropPeer("send failed");
}

void networkLine(const char *line) {
    if (!ready) {
        if (!bench::equal(line, bench::HELLO)) { dropPeer("invalid handshake"); return; }
        if (!sendLine(bench::WELCOME)) { dropPeer("handshake send failed"); return; }
        ready = true;
        lastReply = millis();
        Serial.println("LINK UP: PICO_W; MSP430 is not linked yet");
        return;
    }
    uint32_t id = 0;
    const char *payload = nullptr;
    if (!bench::frame(line, "ACK ", id, payload) || !pending || id != pending) {
        dropPeer("unexpected reply ID or malformed frame"); return;
    }
    const bool matches =
        (bench::equal(expected, "PING") && bench::equal(payload, "PONG PICO_W")) ||
        (bench::equal(expected, "STATUS") && bench::startsWith(payload, "STATUS BOARD=PICO_W ")) ||
        (bench::equal(expected, "LED ON") && bench::equal(payload, "LED=ON")) ||
        (bench::equal(expected, "LED OFF") && bench::equal(payload, "LED=OFF"));
    if (!matches) { dropPeer("reply does not match request"); return; }
    if (!heartbeat) { Serial.print("ROBOT "); Serial.println(payload); }
    pending = 0;
    lastReply = millis();
}

void command(const char *line) {
    if (bench::equal(line, "HELP") || bench::equal(line, "?")) {
        Serial.println("PING | STATUS | ROBOT PING | ROBOT STATUS | ROBOT LED ON | ROBOT LED OFF");
        Serial.println("Uppercase, newline, 115200 baud. LED means Pico onboard LED. No actuator commands.");
    } else if (bench::equal(line, "PING")) Serial.println("PONG ESP32_GATEWAY");
    else if (bench::equal(line, "STATUS")) printStatus();
    else if (bench::startsWith(line, "ROBOT ")) request(line + 6);
    else Serial.println("ERROR unknown command; send HELP");
}

void setup() {
    Serial.begin(115200);
    WiFi.mode(WIFI_AP);
    WiFi.softAPConfig(IPAddress(192,168,4,1), IPAddress(192,168,4,1), IPAddress(255,255,255,0));
    apReady = WiFi.softAP(BENCH_SSID, BENCH_PASSWORD, 6, false, 1);
    if (apReady) server.begin();
    Serial.println("ESP32 laptop gateway v1 - onboard LED bench link only");
    printStatus();
}

void loop() {
    // Bound each pass so an endless byte stream cannot starve timeouts.
    for (unsigned n = 0; n < 128 && Serial.available(); ++n) {
        const auto result = usbLine.push(static_cast<uint8_t>(Serial.read()));
        if (result == bench::Feed::Ready) command(usbLine.text);
        else if (result == bench::Feed::Invalid) Serial.println("ERROR invalid or oversized USB line");
        if (result != bench::Feed::Pending) usbLine.reset();
    }
    if (active && !peer.connected()) dropPeer("Pico disconnected");
    if (apReady && server.hasClient()) {
        WiFiClient incoming = server.accept();
        if (active) incoming.stop();
        else {
            peer = incoming;
            peer.setNoDelay(true);
            active = true;
            connectedAt = millis();
            netLine.reset();
        }
    }
    for (unsigned n = 0; n < 256 && active && peer.available(); ++n) {
        const auto result = netLine.push(static_cast<uint8_t>(peer.read()));
        if (result == bench::Feed::Ready) networkLine(netLine.text);
        else if (result == bench::Feed::Invalid) dropPeer("invalid network line");
        if (result != bench::Feed::Pending) netLine.reset();
    }
    const uint32_t now = millis();
    if (active && !ready && bench::expired(now, connectedAt, bench::LINK_TIMEOUT_MS))
        dropPeer("handshake timeout");
    if (pending && bench::expired(now, sentAt, bench::REPLY_TIMEOUT_MS))
        dropPeer("reply timeout; command outcome unknown");
    if (ready && !pending && bench::expired(now, lastReply, 1000)) request("PING", true);
    delay(1);
}
