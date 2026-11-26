#include <string_view>
#include "RobotBench.h"

// Run at compile time with the desk action tests. A damaged line must be
// discarded through its terminator before another command can be accepted.
constexpr bool completeLinesOnly() {
    bench::Line<5> line;
    for (char c : std::string_view("PING")) line.push(c);
    if (line.push('\r') != bench::Feed::Pending || line.push('\n') != bench::Feed::Ready ||
        std::string_view(line.text) != "PING") return false;

    line.reset();
    for (char c : std::string_view("TOO LONG PING")) line.push(c);
    if (line.push('\n') != bench::Feed::Invalid) return false;

    line.reset();
    line.push('P');
    line.push(0);
    line.push('I');
    if (line.push('\n') != bench::Feed::Invalid) return false;

    line.reset();
    line.push('S');
    return line.push('\n') == bench::Feed::Ready && std::string_view(line.text) == "S";
}
static_assert(completeLinesOnly());
