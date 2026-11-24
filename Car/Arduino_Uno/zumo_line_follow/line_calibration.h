#pragma once

#include <EEPROM.h>
#include <ZumoShield.h>
#include <stddef.h>
#include "robot_link.h"

namespace LineCalibration {
// Byte 0 selects the last complete record. The flip alarm owns the final two
// EEPROM bytes. Change the selector tags if the sensor order or format changes.
const uint8_t slotA = 0xa6, slotB = 0x59;
const uint8_t sensorCount = 6;
const uint16_t sensorTimeout = 2000;  // ZumoReflectanceSensorArray::init() default

struct Record {
    uint16_t minimum[sensorCount];
    uint16_t maximum[sensorCount];
    uint16_t crc;
};

inline int address(uint8_t slot) {
    return slot == slotA ? 1 : 1 + sizeof(Record);
}

inline void clear() {
    EEPROM.update(0, 0xff);
}

inline uint16_t checksum(const Record &record) {
    return rlCrc(reinterpret_cast<const uint8_t*>(&record), offsetof(Record, crc));
}

inline bool usable(const Record &record) {
    for (uint8_t i = 0; i < sensorCount; ++i) {
        if (record.minimum[i] >= record.maximum[i] || record.maximum[i] > sensorTimeout)
            return false;
    }
    return true;
}

inline bool save(const ZumoReflectanceSensorArray &sensors) {
    if (!sensors.calibratedMinimumOn || !sensors.calibratedMaximumOn) return false;
    Record record;
    for (uint8_t i = 0; i < sensorCount; ++i) {
        record.minimum[i] = sensors.calibratedMinimumOn[i];
        record.maximum[i] = sensors.calibratedMaximumOn[i];
    }
    if (!usable(record)) return false;
    record.crc = checksum(record);
    // Publish the new slot only after every sensor value and the CRC are stored.
    const uint8_t next = EEPROM.read(0) == slotA ? slotB : slotA;
    EEPROM.put(address(next), record);
    EEPROM.update(0, next);
    return true;
}

inline bool restore(ZumoReflectanceSensorArray &sensors) {
    const uint8_t slot = EEPROM.read(0);
    if (slot != slotA && slot != slotB) return false;
    Record record;
    EEPROM.get(address(slot), record);
    if (record.crc != checksum(record) || !usable(record)) return false;
    // Pololu allocates the calibration arrays on the first calibrate() call.
    // The tracks stay parked and we replace that reading with the saved values.
    sensors.calibrate();
    if (!sensors.calibratedMinimumOn || !sensors.calibratedMaximumOn) return false;
    for (uint8_t i = 0; i < sensorCount; ++i) {
        sensors.calibratedMinimumOn[i] = record.minimum[i];
        sensors.calibratedMaximumOn[i] = record.maximum[i];
    }
    return true;
}
}
