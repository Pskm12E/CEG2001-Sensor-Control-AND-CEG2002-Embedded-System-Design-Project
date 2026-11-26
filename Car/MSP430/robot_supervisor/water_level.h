#ifndef WATER_LEVEL_H
#define WATER_LEVEL_H
#include <stdint.h>

enum { WATER_LOW_THRESHOLD=500, REFILL_DISABLED=4096 };
#if defined(TANK_EMPTY_ADC) && defined(TANK_FULL_ADC)
#if TANK_EMPTY_ADC < 0 || TANK_FULL_ADC > 4095 || TANK_FULL_ADC <= TANK_EMPTY_ADC
#error Invalid_tank_calibration
#endif
enum { DEFAULT_REFILL_RAW=TANK_EMPTY_ADC + (TANK_FULL_ADC-TANK_EMPTY_ADC)*3/5 + 1 };
#else
enum { DEFAULT_REFILL_RAW=REFILL_DISABLED };
#endif
enum { WATER_STALE_TICKS=30 }; /* 3 seconds at 10 Hz; normal ADC period is 1 second. */
typedef struct { uint8_t empty, consecutive; } WaterLevel;
enum RefillMode { REFILL_WATCH, REFILL_WAIT, REFILL_START, REFILL_OFF };
typedef struct {
    uint16_t minimum, since;
    enum RefillMode mode;
    uint8_t timing;
} Refill;

/* Update level with one completed raw ADC sample. Normally two readings below
 * 500 enter empty and two above 500 clear it. If the calibrated restart minimum
 * is 500 or lower, it becomes the boundary and equality counts as wet.
 * Return true only on entry to empty. */
static uint8_t waterBecameEmpty(WaterLevel *level, uint16_t raw, uint16_t minimum) {
    uint16_t low = minimum <= WATER_LOW_THRESHOLD ? minimum : (uint16_t)WATER_LOW_THRESHOLD;
    uint16_t wet = minimum <= WATER_LOW_THRESHOLD ? minimum : WATER_LOW_THRESHOLD+1u;
    if (level->empty ? raw < wet : raw >= low) {
        level->consecutive=0;
        return 0;
    }
    if (++level->consecutive < 2u) return 0;
    level->consecutive=0;
    level->empty=!level->empty;
    return level->empty;
}
#endif
