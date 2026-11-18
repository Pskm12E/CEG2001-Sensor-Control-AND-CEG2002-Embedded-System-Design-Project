/* Button-driven, bounded GPIO pulse for a disconnected-load voltage test.
 * Tick every ~10 ms. A debounced press starts a pulse; holding cannot repeat it.
 */
#ifndef PUMP_VOLTAGE_PULSE_TEST_H
#define PUMP_VOLTAGE_PULSE_TEST_H
#include <stdint.h>

enum { PT_WAIT_RELEASE, PT_WAIT_PRESS, PT_ACTIVE_HELD, PT_ACTIVE_READY };
enum { PT_DEBOUNCE_TICKS = 3, PT_ON_TICKS = 300, PT_BLINK_HALF_TICKS = 25 };
typedef struct {
    uint16_t remaining;
    uint8_t phase, stable;
} PulseTest;

static uint8_t pulseStable(PulseTest *p, uint8_t condition) {
    if (!condition) p->stable = 0;
    else if (p->stable < PT_DEBOUNCE_TICKS) ++p->stable;
    return p->stable >= PT_DEBOUNCE_TICKS;
}

static uint8_t pulseActive(const PulseTest *p) {
    return p->phase == PT_ACTIVE_HELD || p->phase == PT_ACTIVE_READY;
}

static uint8_t pulseLedOn(const PulseTest *p) {
    return pulseActive(p) && ((PT_ON_TICKS - p->remaining) / PT_BLINK_HALF_TICKS) % 2 == 0;
}

static uint8_t pulseTick(PulseTest *p, uint8_t pressed) {
    if (p->phase == PT_WAIT_RELEASE) {
        if (pulseStable(p, !pressed)) {
            p->phase = PT_WAIT_PRESS; p->stable = 0;
        }
    } else if (p->phase == PT_WAIT_PRESS) {
        if (pulseStable(p, pressed)) {
            p->phase = PT_ACTIVE_HELD; p->remaining = PT_ON_TICKS; p->stable = 0;
        }
    } else if (pulseActive(p)) {
        uint8_t cancel = 0;
        if (p->phase == PT_ACTIVE_HELD) {
            if (pulseStable(p, !pressed)) {
                p->phase = PT_ACTIVE_READY; p->stable = 0;
            }
        } else cancel = pulseStable(p, pressed);
        if (cancel || !p->remaining || --p->remaining == 0) {
            p->remaining = 0; p->phase = PT_WAIT_RELEASE; p->stable = 0;
        }
    } else {
        p->remaining = 0; p->phase = PT_WAIT_RELEASE; p->stable = 0;
    }
    return pulseActive(p);
}
#endif
