#ifndef WATER_LEVEL_H
#define WATER_LEVEL_H
#include <stdint.h>

enum { WATER_LOW_THRESHOLD=500, WATER_REFILLED_RAW=WATER_LOW_THRESHOLD+1 };
enum { WATER_STALE_TICKS=30 }; /* 3 seconds at 10 Hz; normal ADC period is 1 second. */
typedef struct { uint8_t empty, consecutive; } WaterLevel;

/* Two consecutive samples strictly on the other side of 500 change state.
 * Exactly 500 breaks the streak. Return true only on entry to empty. */
static uint8_t waterBecameEmpty(WaterLevel *level, uint16_t raw) {
    if (level->empty ? raw < WATER_REFILLED_RAW : raw >= WATER_LOW_THRESHOLD) {
        level->consecutive=0;
        return 0;
    }
    if (++level->consecutive < 2u) return 0;
    level->consecutive=0;
    level->empty=!level->empty;
    return level->empty;
}
#endif
