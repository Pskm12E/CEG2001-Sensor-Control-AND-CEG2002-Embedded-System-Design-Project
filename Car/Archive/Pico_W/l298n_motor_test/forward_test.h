#pragma once

#include <cstdint>

// One forward pulse per f command. Repeated f commands cannot extend a pulse.
class ForwardTest {
public:
    static constexpr std::uint64_t duration_ms = 1000;

    void update(std::uint64_t now_ms, bool connected, int command) {
        if (!connected) {
            running_ = false;
            return;
        }
        if (running_ && now_ms >= stop_at_ms_) {
            running_ = false;
            return;
        }
        if (command == 's' || command == 'S') {
            running_ = false;
        } else if (!running_ && (command == 'f' || command == 'F')) {
            stop_at_ms_ = now_ms + duration_ms;
            running_ = true;
        }
    }

    bool running() const { return running_; }

private:
    bool running_ = false;
    std::uint64_t stop_at_ms_ = 0;
};
