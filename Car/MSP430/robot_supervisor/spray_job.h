/* Bounded target job. All time values use the supervisor's ~100 ms tick.
 * The build profile explicitly enables the pump output for the installed driver.
 */
#ifndef SPRAY_JOB_H
#define SPRAY_JOB_H
#include <stdint.h>

#ifndef PUMP_DRIVER_VERIFIED
#define PUMP_DRIVER_VERIFIED 0
#endif
/* Port 1 gate output. Use the alternate build for a driver wired to P1.4. */
#if defined(PUMP_GATE_P14) && PUMP_GATE_P14
#define PUMP_GATE_MASK (1u << 4)
#else
#define PUMP_GATE_MASK (1u << 6)
#endif
#ifndef PUMP_SPRAY_TICKS
#define PUMP_SPRAY_TICKS 30u
#endif
#if PUMP_SPRAY_TICKS < 1 || PUMP_SPRAY_TICKS > 30
#error Spray_duration_must_be_between_100ms_and_3_seconds
#endif

enum { SJ_IDLE, SJ_STOPPING, SJ_WAIT_LINK, SJ_SETTLING, SJ_SPRAYING,
       SJ_RESUMING, SJ_COMPLETE, SJ_ABORTED, SJ_DRIVER_DISABLED };
typedef struct {
    uint32_t id;
    volatile uint16_t since; /* Shared with the independent pump cutoff ISR. */
    uint16_t began;
    uint8_t phase;
    uint8_t resumeQueued;
    volatile uint8_t pump;
} SprayJob;

static uint8_t sprayActive(const SprayJob *s) {
    return s->phase >= SJ_STOPPING && s->phase <= SJ_RESUMING;
}
static void sprayCancel(SprayJob *s) {
    s->pump = 0;
    s->resumeQueued = 0;
    if (sprayActive(s)) s->phase = SJ_ABORTED;
}
static uint8_t sprayBegin(SprayJob *s, uint16_t now, uint32_t id, uint8_t eligible) {
    if (!id || !eligible || sprayActive(s) || id == s->id) return 0;
    s->id = id;
    s->began = s->since = now;
    s->pump = 0;
    s->resumeQueued = 0;
    s->phase = SJ_STOPPING;
    return 1;
}
static void sprayStopAck(SprayJob *s, uint16_t now, uint8_t stopped) {
    if (s->phase != SJ_STOPPING) return;
    if (!stopped) { sprayCancel(s); return; }
    s->phase = SJ_WAIT_LINK;
    s->since = now;
}
/* The completed pulse waits for a token-matched continuation from fresh laptop
 * observations. Camera/network loss therefore cannot auto-resume the robot. */
static uint8_t sprayTick(SprayJob *s, uint16_t now, uint8_t ready,
                         uint8_t blocked, uint8_t driverVerified) {
    if (!sprayActive(s)) return 0;
    if (blocked || (uint16_t)(now - s->began) >= 100u) {
        sprayCancel(s); return 0;
    }
    if (s->phase == SJ_STOPPING) {
        if ((uint16_t)(now - s->since) >= 10u) sprayCancel(s);
    } else if (s->phase == SJ_WAIT_LINK) {
        if (ready) { s->phase = SJ_SETTLING; s->since = now; }
        else if ((uint16_t)(now - s->since) >= 20u) sprayCancel(s);
    } else if (s->phase == SJ_SETTLING) {
        if (!ready) { sprayCancel(s); return 0; }
        if ((uint16_t)(now - s->since) >= 3u) {
            s->since = now;
            if (!driverVerified) s->phase = SJ_DRIVER_DISABLED;
            else { s->pump = 1; s->phase = SJ_SPRAYING; }
        }
    } else if (s->phase == SJ_SPRAYING) {
        if (!ready) { sprayCancel(s); return 0; }
        if ((uint16_t)(now - s->since) >= PUMP_SPRAY_TICKS) {
            s->pump = 0;
            s->phase = SJ_RESUMING;
            s->since = now;
        }
    } else if (s->phase == SJ_RESUMING && (uint16_t)(now - s->since) >= 30u) {
        sprayCancel(s);
    }
    return 0;
}
static uint8_t sprayAllowResume(SprayJob *s,uint32_t id,uint8_t ready) {
    if(s->phase!=SJ_RESUMING || s->pump || s->resumeQueued || id!=s->id || !ready) return 0;
    s->resumeQueued=1;
    return 1;
}
static void sprayResumeAck(SprayJob *s, uint8_t moving) {
    if (s->phase == SJ_RESUMING) s->phase = moving ? SJ_COMPLETE : SJ_ABORTED;
}
#endif
