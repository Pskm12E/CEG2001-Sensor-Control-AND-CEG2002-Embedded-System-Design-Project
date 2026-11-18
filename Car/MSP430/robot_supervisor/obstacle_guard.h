/* HC-SR04 stop policy. Only a valid near reading inhibits motion.
 * Missing/stale echoes remain diagnostic faults, not motor STOP conditions.
 * ticks are the existing 100 ms supervisor ticks.
 */
#ifndef OBSTACLE_GUARD_H
#define OBSTACLE_GUARD_H
#include <stdint.h>

/* Current user-selected thresholds; these are not measured braking distances. */
#define OBSTACLE_STOP_CM 5u
#define OBSTACLE_RELEASE_CM 7u
#define OBSTACLE_STALE_TICKS 3u

typedef struct {
    uint16_t cm, lastValid;
    uint8_t haveValid, valid, inhibit, clearCount, fault;
} ObstacleGuard;

static void obstacleInit(ObstacleGuard *s) {
    s->cm = s->lastValid = 0;
    s->haveValid = s->valid = s->clearCount = 0;
    s->inhibit = 0;
    s->fault = 1;
}

static void obstacleAge(ObstacleGuard *s, uint16_t now) {
    if (!s->haveValid || (uint16_t)(now - s->lastValid) >= OBSTACLE_STALE_TICKS) {
        s->valid = 0;
        s->inhibit = 0;
        s->fault = 1;
        s->clearCount = 0;
    }
}

static void obstacleSample(ObstacleGuard *s, uint16_t now, uint16_t cm, uint8_t valid) {
    s->valid = valid && cm >= 2u && cm <= 400u;
    if (!s->valid) {
        s->clearCount = 0;
        obstacleAge(s, now);
        return;
    }

    s->cm = cm;
    s->lastValid = now;
    s->haveValid = 1;
    s->fault = 0;
    if (cm <= OBSTACLE_STOP_CM) {
        s->inhibit = 1;
        s->clearCount = 0;
    } else if (cm >= OBSTACLE_RELEASE_CM) {
        if (s->clearCount < 2u) ++s->clearCount;
        if (s->clearCount >= 2u) s->inhibit = 0;
    } else {
        s->clearCount = 0;
    }
}

/* SMCLK = REFO(32768) * 32 = 1048576 Hz in main.c. Approx. sound speed 343m/s. */
static uint16_t obstacleCmFromCounts(uint16_t width) {
    return (uint16_t)(((uint32_t)width * 34300ul + 1048576ul) / 2097152ul);
}
#endif
