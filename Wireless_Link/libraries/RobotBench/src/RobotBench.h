#pragma once
#include <stddef.h>
#include <stdint.h>

// This protocol is for onboard-LED diagnostics only. It is NOT an actuator bus.
namespace bench {
constexpr uint16_t PORT = 4242;
constexpr uint32_t REPLY_TIMEOUT_MS = 2000;
constexpr uint32_t LINK_TIMEOUT_MS = 5000;
constexpr const char *HELLO = "HELLO PICO_W BENCH1";
constexpr const char *WELCOME = "WELCOME BENCH1";

constexpr bool equal(const char *a, const char *b) {
    while (*a && *a == *b) { ++a; ++b; }
    return *a == *b;
}
constexpr bool startsWith(const char *text, const char *prefix) {
    while (*prefix) if (*text++ != *prefix++) return false;
    return true;
}
constexpr bool allowed(const char *command) {
    return equal(command, "PING") || equal(command, "STATUS") ||
           equal(command, "LED ON") || equal(command, "LED OFF");
}

enum class Feed { Pending, Ready, Invalid };
template<size_t N> struct Line {
    char text[N]{};
    size_t size = 0;
    bool invalid = false;
    bool cr = false;
    constexpr void reset() { size = 0; invalid = cr = false; text[0] = '\0'; }
    // Caller consumes text, then resets after Ready/Invalid. Drop oversized or
    // binary lines through the newline, never interpret their suffix as a command.
    constexpr Feed push(uint8_t c) {
        if (c == '\n') {
            text[size] = '\0';
            return invalid || size == 0 ? Feed::Invalid : Feed::Ready;
        }
        if (invalid) return Feed::Pending;
        if (cr) { invalid = true; return Feed::Pending; }
        if (c == '\r') { cr = true; return Feed::Pending; }
        if (c < 32 || c > 126 || size + 1 >= N) invalid = true;
        else text[size++] = static_cast<char>(c);
        return Feed::Pending;
    }
};

// Strict positive decimal ID. An ID belongs only to its current TCP connection.
constexpr bool frame(const char *line, const char *prefix,
                     uint32_t &id, const char *&payload) {
    if (!startsWith(line, prefix)) return false;
    while (*prefix++) ++line;
    if (*line < '1' || *line > '9') return false;
    uint32_t number = 0;
    while (*line >= '0' && *line <= '9') {
        const uint32_t digit = static_cast<uint32_t>(*line++ - '0');
        if (number > (UINT32_MAX - digit) / 10) return false;
        number = number * 10 + digit;
    }
    if (*line++ != ' ' || !*line) return false;
    id = number;
    payload = line;
    return true;
}
constexpr bool expired(uint32_t now, uint32_t since, uint32_t limit) {
    return static_cast<uint32_t>(now - since) >= limit;
}
} // namespace bench
