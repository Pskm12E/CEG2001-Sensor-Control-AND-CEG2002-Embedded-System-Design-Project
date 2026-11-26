#ifndef ROBOT_CONTROL_H
#define ROBOT_CONTROL_H
#include <stdint.h>
#include "../../../Arduino_Uno/zumo_line_follow/robot_link.h"

/* No hardware dependencies: the exact navigation/lease code is also host-tested. */
enum DriveAction { DRIVE_STOP, DRIVE_FORWARD, DRIVE_LEFT, DRIVE_RIGHT };
// Track geometry is separate from sensor polarity, which calibration learns.
enum LineLayout { BLACK_UNDER_BOTH, WHITE_LANE, BLACK_BETWEEN_SENSORS };
struct LineSensor {
    // Uno ADC units. Legacy digital callers still use 0/1 with analogInput=false.
    static const uint16_t MIN_CONTRAST=40, HYSTERESIS=8, MAX_CAPTURE_SPREAD=30;
    int16_t white=-1, black=-1;
    uint16_t raw=0;
    uint8_t candidate=0, stable=0;
    uint32_t since=0;
    bool settled=false, analogInput=false, classified=false;
    uint16_t span() const { return white>black?white-black:black-white; }
    int16_t threshold() const { return (white+black)/2; }
    bool calibrated() const {
        return white>=0 && black>=0 && (analogInput?span()>=MIN_CONTRAST:white!=black);
    }
    bool isBlack() const { return calibrated() && settled && stable==(analogInput?1:black); }
    void sample(uint16_t value, uint32_t now) {
        raw=value;
        if(analogInput) {
            if(!calibrated()) { settled=classified=false; return; }
            const int16_t delta=int16_t(value)-threshold();
            if(delta>=int16_t(HYSTERESIS)) { value=black>white?1:0; classified=true; }
            else if(delta<=-int16_t(HYSTERESIS)) { value=black>white?0:1; classified=true; }
            else if(!classified) { settled=false; return; }
            else value=candidate; // Retain the last class inside the hysteresis band.
        }
        if(value!=candidate) { candidate=value; since=now; settled=false; }
        else if(uint32_t(now-since)>=8) { stable=value; settled=true; }
    }
};
class RobotControl {
public:
    // Legacy tests retain 750ms by default; the active Uno sketch passes its
    // explicit TURN_LIMIT_MS setting (currently 3000ms for slow corners).
    explicit RobotControl(bool followWhite=false,uint32_t cornerLimitMs=750)
        :RobotControl(followWhite?WHITE_LANE:BLACK_UNDER_BOTH,cornerLimitMs) {}
    explicit RobotControl(LineLayout layout,uint32_t cornerLimitMs=750,bool analogInputs=false)
        :lineLayout(layout),turnLimitMs(cornerLimitMs) {
        for(uint8_t i=0;i<2;++i) sensors[i].analogInput=analogInputs;
    }
    static const uint32_t LEASE_MS=1000;
    LineSensor sensors[2];
    bool following=false;
    DriveAction action=DRIVE_STOP;
    uint8_t reason=RL_OK, calibration=0;
    uint16_t session=0, sequence=0;
    uint32_t lastLease=0;
    uint8_t userRequest=0;

    bool requestLocal(uint8_t op) {
        if(!session || following || calibration || userRequest) return false;
        if(op==RL_WHITE) userRequest=RL_USER_WHITE;
        else if(op==RL_BLACK) userRequest=RL_USER_BLACK;
        else if(op==RL_CLEAR) userRequest=RL_USER_CLEAR;
        else if(op==RL_START) userRequest=RL_USER_START;
        else return false;
        return true;
    }

    bool calibrated() const { return sensors[0].calibrated() && sensors[1].calibrated(); }
    uint8_t flags() const {
        return (calibrated()?RL_CAL:0) | (sensors[0].isBlack()?RL_LEFT_BLACK:0) |
            (sensors[1].isBlack()?RL_RIGHT_BLACK:0) | (following?RL_MOVING:0) |
            (reason>=RL_LEASE_LOST?RL_FAULT:0) | (sensors[0].settled?RL_LEFT_STABLE:0) |
            (sensors[1].settled?RL_RIGHT_STABLE:0) | (calibration?RL_CALIBRATING:0);
    }
    void stop(uint8_t why, bool invalidate=true) {
        following=false; action=DRIVE_STOP; losing=turning=uncertain=false;
        lastTurn=DRIVE_STOP; reason=why; calibration=0;
        userRequest=0;
        if(invalidate) { session=0; sequence=0; lastType=0; }
    }
    void tick(uint32_t now, uint16_t left, uint16_t right) {
        sensors[0].sample(left,now); sensors[1].sample(right,now);
        /* Enforce expiry before processing any newly arrived command. */
        if(following && uint32_t(now-lastLease)>=LEASE_MS) stop(RL_LEASE_LOST);
        if(calibration && uint32_t(now-lastSample)>=5) {
            lastSample=now; ++sampleCount;
            const uint16_t values[2]={left,right};
            for(uint8_t i=0;i<2;++i) {
                totals[i]+=values[i];
                if(values[i]<minimums[i]) minimums[i]=values[i];
                if(values[i]>maximums[i]) maximums[i]=values[i];
            }
            if(sampleCount==40) {
                bool good=true;
                for(uint8_t i=0;i<2;++i) {
                    int16_t value=-1;
                    if(sensors[i].analogInput) {
                        if(maximums[i]-minimums[i]<=LineSensor::MAX_CAPTURE_SPREAD)
                            value=(totals[i]+20)/40;
                        else good=false;
                    } else if(totals[i]<=2) value=0;
                    else if(totals[i]>=38) value=1;
                    else good=false;
                    if(calibration==RL_WHITE) sensors[i].white=value;
                    else sensors[i].black=value;
                    sensors[i].settled=sensors[i].classified=false; sensors[i].since=now;
                }
                calibration=0; reason=good?RL_OK:RL_CAL_UNSTABLE;
            }
        }
        if(!following) { action=DRIVE_STOP; return; }
        if(!calibrated()) { stop(RL_NOT_CAL); return; }
        if(!sensors[0].settled || !sensors[1].settled) {
            action=DRIVE_STOP;
            if(!uncertain) { uncertain=true; uncertainSince=now; }
            if(uint32_t(now-uncertainSince)>=150) stop(RL_UNSTABLE);
            return;
        }
        uncertain=false;
        const bool l=sensors[0].isBlack(), r=sensors[1].isBlack();
        if(lineLayout!=BLACK_UNDER_BOTH) {
            if(!l && !r) { turning=false; action=DRIVE_FORWARD; }
            else if(l && r) stop(RL_BOTH_BLACK);
            else {
                if(!turning) { turning=true; turnSince=now; }
                if(uint32_t(now-turnSince)>=turnLimitMs) { stop(RL_TURN_TIMEOUT); return; }
                // A line between the heads is approached; white-lane borders
                // are avoided. Both layouts are white/white when centred.
                action=lineLayout==BLACK_BETWEEN_SENSORS
                    ? (l?DRIVE_LEFT:DRIVE_RIGHT) : (l?DRIVE_RIGHT:DRIVE_LEFT);
            }
            return;
        }
        if(l && r) { losing=turning=false; action=DRIVE_FORWARD; }
        else if(l || r) {
            losing=false;
            if(!turning) { turning=true; turnSince=now; }
            if(uint32_t(now-turnSince)>=turnLimitMs) { stop(RL_TURN_TIMEOUT); return; }
            action=l?DRIVE_LEFT:DRIVE_RIGHT; lastTurn=action; lastTurnSeen=now;
        } else {
            if(!losing) { losing=true; lossSince=now; }
            if(lastTurn==DRIVE_STOP || uint32_t(now-lossSince)>=250 ||
               uint32_t(now-lastTurnSeen)>=250 || (turning && uint32_t(now-turnSince)>=turnLimitMs))
                stop(RL_LINE_LOST);
            else action=lastTurn;
        }
    }
    RlPacket handle(const RlPacket &p, uint32_t now) {
        uint8_t result=RL_OK;
        if(following && uint32_t(now-lastLease)>=LEASE_MS) stop(RL_LEASE_LOST);
        if(p.arg || p.detail || p.type<RL_HELLO || p.type>RL_CLEAR) {
            stop(RL_BAD_FRAME); result=RL_BAD_COMMAND;
        } else if(p.type==RL_STOP) {
            stop(RL_OK); // STOP is accepted even without a negotiated session.
        } else if(p.type==RL_HELLO && p.session && p.seq==0) {
            stop(RL_OK); session=p.session; sequence=0; lastType=RL_HELLO;
        } else if(!session || p.session!=session) {
            result=RL_BAD_SESSION;
        } else if(p.seq==sequence && p.type==lastType) {
            // Duplicate: return current state, never renew lease or restart calibration.
            result=lastResult;
        } else if(sequence==65535u || p.seq!=uint16_t(sequence+1u)) {
            result=RL_BAD_SEQUENCE;
        } else {
            sequence=p.seq; lastType=p.type;
            if(p.type==RL_WHITE || p.type==RL_BLACK || p.type==RL_CLEAR || p.type==RL_START)
                userRequest=0;
            switch(p.type) {
            case RL_STATUS: result=reason; break;
            case RL_WHITE: case RL_BLACK:
                stop(RL_OK,false); calibration=p.type; sampleCount=0;
                lastSample=now;
                for(uint8_t i=0;i<2;++i) {
                    totals[i]=maximums[i]=0; minimums[i]=1023;
                    sensors[i].settled=sensors[i].classified=false;
                    if(p.type==RL_WHITE) sensors[i].white=-1; else sensors[i].black=-1;
                }
                break;
            case RL_CLEAR:
                stop(RL_OK,false);
                for(uint8_t i=0;i<2;++i) {
                    sensors[i].white=sensors[i].black=-1;
                    sensors[i].settled=sensors[i].classified=false;
                }
                break;
            case RL_START:
                if(calibration) result=RL_CAL_BUSY;
                else if(!calibrated()) result=RL_NOT_CAL;
                else if(!sensors[0].settled || !sensors[1].settled ||
                        (lineLayout!=BLACK_UNDER_BOTH ? (sensors[0].isBlack() || sensors[1].isBlack())
                                   : (!sensors[0].isBlack() || !sensors[1].isBlack()))) result=RL_NOT_CENTER;
                else if(!following) {
                    following=true; reason=RL_OK; lastLease=now;
                    losing=turning=uncertain=false; lastTurn=DRIVE_STOP;
                    action=DRIVE_FORWARD;
                }
                break;
            case RL_KEEP:
                if(following) lastLease=now;
                else result=reason ? reason : uint8_t(RL_LOCAL_STOP);
                break;
            default: result=RL_BAD_COMMAND; break;
            }
            lastResult=result;
        }
        if(p.type==RL_STATUS && userRequest && session && p.session==session &&
           p.seq==sequence && lastType==RL_STATUS && !following &&
           (result==RL_OK || result==reason)) result=userRequest;
        RlPacket reply={uint8_t(p.type|RL_REPLY),p.session,p.seq,flags(),result};
        return reply;
    }
private:
    const LineLayout lineLayout;
    const uint32_t turnLimitMs;
    bool losing=false, turning=false, uncertain=false;
    DriveAction lastTurn=DRIVE_STOP;
    uint32_t lossSince=0, turnSince=0, uncertainSince=0, lastTurnSeen=0, lastSample=0;
    uint16_t totals[2]={0,0}, minimums[2]={1023,1023}, maximums[2]={0,0};
    uint8_t sampleCount=0, lastType=0, lastResult=RL_OK;
};
#endif
