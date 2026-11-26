#pragma once
#include <stddef.h>
#include <stdint.h>

// Bounded line input shared by the FireBeetle gateway and desk Pico W.
namespace bench {
enum class Feed { Pending, Ready, Invalid };
template<size_t N> struct Line {
    char text[N]{};
    size_t size = 0;
    bool invalid = false;
    bool cr = false;
    // Release the previous line and clear its overflow flag before collecting another.
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
} // namespace bench
