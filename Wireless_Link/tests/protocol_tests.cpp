#include "RobotBench.h"
// Compile-time tests run as part of the actual Pico build. No host EXE required.
constexpr bool frames() {
    uint32_t id = 0; const char *payload = nullptr;
    if (!bench::frame("REQ 42 LED ON", "REQ ", id, payload) || id != 42 || !bench::equal(payload, "LED ON")) return false;
    if (bench::frame("REQ 0 PING", "REQ ", id, payload)) return false;
    if (bench::frame("REQ 01 PING", "REQ ", id, payload)) return false;
    if (bench::frame("REQ 4294967296 PING", "REQ ", id, payload)) return false;
    if (bench::frame("REQ 12X PING", "REQ ", id, payload)) return false;
    if (bench::frame("REQ 1 ", "REQ ", id, payload)) return false;
    if (bench::frame("REQ 1", "REQ ", id, payload)) return false;
    if (bench::frame("ACK 1 PING", "REQ ", id, payload)) return false;
    return bench::frame("ACK 4294967295 PONG PICO_W", "ACK ", id, payload) && id == UINT32_MAX;
}
constexpr bool lines() {
    bench::Line<5> line;
    for (char c : "PING") { if (c) line.push(c); }
    if (line.push('\r') != bench::Feed::Pending || line.push('\n') != bench::Feed::Ready || !bench::equal(line.text, "PING")) return false;
    line.reset();
    for (char c : "TOO LONG PING") { if (c) line.push(c); }
    if (line.push('\n') != bench::Feed::Invalid) return false;
    line.reset(); line.push('P'); line.push(0); line.push('I');
    if (line.push('\n') != bench::Feed::Invalid) return false;
    line.reset(); line.push('P'); line.push('\r'); line.push('I');
    if (line.push('\n') != bench::Feed::Invalid) return false;
    line.reset();
    return line.push('\n') == bench::Feed::Invalid;
}
static_assert(frames(), "Frame parsing must reject malformed and overflow IDs");
static_assert(lines(), "Line framing must reject oversized, binary and malformed CRLF input");
static_assert(bench::allowed("PING") && bench::allowed("STATUS") && bench::allowed("LED ON") && bench::allowed("LED OFF"));
static_assert(!bench::allowed("SPRAY") && !bench::allowed("FORWARD") && !bench::allowed("LED ON EXTRA"));
static_assert(bench::expired(15, UINT32_MAX - 9, 25), "Timeout must survive millisecond wrap");
static_assert(!bench::expired(14, UINT32_MAX - 9, 25));
