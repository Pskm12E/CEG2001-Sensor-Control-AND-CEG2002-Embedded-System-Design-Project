#pragma once

#include <EEPROM.h>
#include <Wire.h>
#include <ZumoShield.h>

class FlipAlarm {
public:
    void begin() {
        // Keep the existing mute byte across upgrades. An erased reference
        // stays unknown until the operator calibrates with the tracks down.
        enabled = EEPROM.read(EEPROM.length() - 1) != muteMarker;
        const uint8_t reference = EEPROM.read(EEPROM.length() - 2);
        if (reference == '+') uprightSign = 1;
        if (reference == '-') uprightSign = -1;
        Wire.begin();
        Wire.setWireTimeout(3000, true);
    }

    void setEnabled(bool value) {
        if (enabled == value) return;
        enabled = value;
        EEPROM.update(EEPROM.length() - 1, value ? 0xff : muteMarker);
        clearAlarm();
        levelSamples = 0;
        sensorReady = false;
        nextSample = millis();
    }

    void service(uint32_t now, bool calibratingAtRest) {
        if (!calibratingAtRest) levelSamples = 0;
        if ((!enabled && !calibratingAtRest) || int32_t(now - nextSample) < 0) return;
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
            levelSamples = 0;
            sensorReady = false;
            nextSample = now + retryMs;
            return;
        }
        if (uint32_t(now - nextSample) > sampleMs * 2U) {
            consecutive = 0;
            levelSamples = 0;
        }
        nextSample = now + sampleMs;
        z = imu.a.z;
        if (calibratingAtRest) {
            clearAlarm();
            learnUpright();
            return;
        }
        if (!enabled || !uprightSign) return;
        // Widen before negating: -32768 is a valid raw accelerometer sample.
        const int32_t invertedZ = uprightSign > 0 ? -int32_t(z) : int32_t(z);
        if (!flipped) {
            consecutive = invertedZ > flippedZCounts ? consecutive + 1 : 0;
            if (consecutive >= flippedSamples) {
                flipped = true;
                consecutive = 0;
                nextBeep = now;
            }
        } else {
            consecutive = invertedZ < clearZCounts ? consecutive + 1 : 0;
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
    int8_t uprightSign = 0;

private:
    static const uint8_t muteMarker = 0xa6;
    static const uint8_t sampleMs = 40;
    static const uint16_t retryMs = 2000;
    // Separate entry and exit thresholds prevent chatter while the car rocks.
    static const int16_t flippedZCounts = 11500;
    static const int16_t clearZCounts = 4000;
    static const uint8_t flippedSamples = 11;
    static const uint8_t clearSamples = 4;
    static const uint8_t requiredLevelSamples = 8;
    ZumoIMU imu;
    ZumoBuzzer buzzer;
    uint8_t consecutive = 0;
    uint8_t levelSamples = 0;
    int8_t candidateSign = 0;
    void learnUpright() {
        // Accept approximately one g on Z for consecutive parked readings.
        const int32_t magnitude = z < 0 ? -int32_t(z) : int32_t(z);
        const int8_t sign = z > 0 ? 1 : -1;
        if (magnitude < 14500 || magnitude > 18000 || sign == uprightSign) {
            levelSamples = 0;
            return;
        }
        if (sign != candidateSign) {
            candidateSign = sign;
            levelSamples = 0;
        }
        if (++levelSamples == requiredLevelSamples) {
            uprightSign = sign;
            EEPROM.update(EEPROM.length() - 2, sign > 0 ? '+' : '-');
            levelSamples = 0;
        }
    }
    uint32_t nextSample = 0;
    uint32_t nextBeep = 0;

    void clearAlarm() {
        if (flipped) buzzer.stopPlaying();
        flipped = false;
        consecutive = 0;
    }
};
