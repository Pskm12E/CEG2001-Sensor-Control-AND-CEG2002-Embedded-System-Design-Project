#ifndef WATER_LEVEL_H
#define WATER_LEVEL_H
#include <stdint.h>

enum { WATER_EMPTY_RAW=15, WATER_REFILLED_RAW=30 };
typedef struct { uint8_t empty, consecutive; } WaterLevel;

/* Called once per completed ADC conversion. Return true only on entry to
 * empty. A higher refill threshold prevents chatter at the dry reading. */
static uint8_t waterBecameEmpty(WaterLevel *level, uint16_t raw) {
    if (level->empty ? raw < WATER_REFILLED_RAW : raw > WATER_EMPTY_RAW) {
        level->consecutive=0;
        return 0;
    }
    if (++level->consecutive < 2u) return 0;
    level->consecutive=0;
    level->empty=!level->empty;
    return level->empty;
}
#endif
