#pragma once

#include <EEPROM.h>
#include <Wire.h>
#include <ZumoShield.h>

class FlipAlarm {
public:
    void begin() {
        // Erased EEPROM defaults to enabled. Reserve the last byte for mute.
        enabled = EEPROM.read(EEPROM.length() - 1) != muteMarker;
        Wire.begin();
        Wire.setWireTimeout(3000, true);
    }

    void setEnabled(bool value) {
        if (enabled == value) return;
        enabled = value;
        EEPROM.update(EEPROM.length() - 1, value ? 0xff : muteMarker);
        clearAlarm();
        sensorReady = false;
        nextSample = millis();
    }

    void service(uint32_t now) {
        if (!enabled || int32_t(now - nextSample) < 0) return;
        if (!sensorReady) {
            if (imu.init()) {
                imu.enableDefault();
                sensorReady = imu.getLastError() == 0;
            }
            nextSample = now + (sensorReady ? sampleMs : retryMs);
            return;
        }
        imu.readAcc();
        if (imu.getLastError()) {
            clearAlarm();
            sensorReady = false;
            nextSample = now + retryMs;
            return;
        }
        // A gap in readings breaks the run of samples used to confirm a flip.
        if (uint32_t(now - nextSample) > sampleMs * 2U) consecutive = 0;
        nextSample = now + sampleMs;
        z = imu.a.z;
        // This mounted shield reads about -15700 upright. Positive Z points
        // through the chassis toward the ground. One g is about 16384 counts.
        if (!flipped) {
            consecutive = z > flippedZCounts ? consecutive + 1 : 0;
            if (consecutive >= flippedSamples) {
                flipped = true;
                consecutive = 0;
                nextBeep = now;
            }
        } else {
            consecutive = z < clearZCounts ? consecutive + 1 : 0;
            if (consecutive >= clearSamples) clearAlarm();
        }
        if (flipped && int32_t(now - nextBeep) >= 0) {
            buzzer.playFrequency(1800, 120, 10);
            nextBeep = now + 750;
        }
    }

    bool enabled = true;
    bool sensorReady = false;
    bool flipped = false;
    int16_t z = 0;

private:
    static const uint8_t muteMarker = 0xa6;
    static const uint8_t sampleMs = 40;
    static const uint16_t retryMs = 2000;
    // Separate entry and exit thresholds prevent chatter while the car rocks.
    static const int16_t flippedZCounts = 11500;
    static const int16_t clearZCounts = 4000;
    static const uint8_t flippedSamples = 11;
    static const uint8_t clearSamples = 4;
    ZumoIMU imu;
    ZumoBuzzer buzzer;
    uint8_t consecutive = 0;
    uint32_t nextSample = 0;
    uint32_t nextBeep = 0;

    void clearAlarm() {
        if (flipped) buzzer.stopPlaying();
        flipped = false;
        consecutive = 0;
    }
};
