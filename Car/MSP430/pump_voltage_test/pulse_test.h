/* Button-driven, bounded GPIO pulse for a disconnected-load voltage test.
 * Tick every ~10 ms. Start only after a debounced press AND release.
 */
#ifndef PUMP_VOLTAGE_PULSE_TEST_H
#define PUMP_VOLTAGE_PULSE_TEST_H
#include <stdint.h>

enum { PT_WAIT_RELEASE, PT_WAIT_PRESS, PT_WAIT_BUTTON_UP, PT_ACTIVE };
enum { PT_DEBOUNCE_TICKS = 3, PT_ON_TICKS = 300 };
typedef struct {
    uint16_t remaining;
    uint8_t phase, stable;
} PulseTest;

static uint8_t pulseStable(PulseTest *p, uint8_t condition) {
    if (!condition) p->stable = 0;
    else if (p->stable < PT_DEBOUNCE_TICKS) ++p->stable;
    return p->stable >= PT_DEBOUNCE_TICKS;
}

static uint8_t pulseTick(PulseTest *p, uint8_t pressed) {
    if (p->phase == PT_WAIT_RELEASE) {
        if (pulseStable(p, !pressed)) {
            p->phase = PT_WAIT_PRESS; p->stable = 0;
        }
    } else if (p->phase == PT_WAIT_PRESS) {
        if (pulseStable(p, pressed)) {
            p->phase = PT_WAIT_BUTTON_UP; p->stable = 0;
        }
    } else if (p->phase == PT_WAIT_BUTTON_UP) {
        if (pulseStable(p, !pressed)) {
            p->phase = PT_ACTIVE; p->remaining = PT_ON_TICKS; p->stable = 0;
        }
    } else if (p->phase == PT_ACTIVE) {
        if (pulseStable(p, pressed) || !p->remaining || --p->remaining == 0) {
            p->remaining = 0; p->phase = PT_WAIT_RELEASE; p->stable = 0;
        }
    } else {
        p->remaining = 0; p->phase = PT_WAIT_RELEASE; p->stable = 0;
    }
    return p->phase == PT_ACTIVE;
}
#endif
