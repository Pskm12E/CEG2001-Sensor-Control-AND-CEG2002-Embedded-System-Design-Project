// Portable Zumo motion authorisation. The MSP owns grants; Uno owns steering.
#ifndef ZUMO_CONTROL_H
#define ZUMO_CONTROL_H
#include "robot_link.h"

enum ZumoEvent {
    ZE_BOOT, ZE_CALIBRATING, ZE_CAL_DONE, ZE_FOLLOWING, ZE_MSP_STOP,
    ZE_MSP_RESYNC, ZE_HEARTBEAT_LOST, ZE_UART_ERROR, ZE_LOCAL_STOP, ZE_SESSION_ERROR,
    ZE_OBSTACLE_PAUSE, ZE_EMPTY_REVERSE, ZE_REVERSE_DONE, ZE_CAL_RESTORED
};

class ZumoControl {
public:
    static const uint32_t LEASE_MS=1000;
    bool calibrated=false, following=false, calibrating=false;
    bool obstaclePaused=false, reversing=false;
    uint8_t reason=RL_OK, userRequest=0;
    uint8_t lastEvent=ZE_BOOT; // Persists across stopped STOP/HELLO exchanges.
    uint16_t session=0, sequence=0;
    uint32_t lastLease=0, lastReverseGrant=0;

    bool moving() const { return following || calibrating || reversing; }
    uint8_t flags() const {
        // MOVING includes authorisation for the calibration sweep's initial wait.
        return (calibrated?RL_CAL:0) | (moving()?RL_MOVING:0) |
            (calibrating?RL_CALIBRATING:0) | (reversing?RL_ZUMO_REVERSING:0) |
            (reason>=RL_LEASE_LOST?RL_FAULT:0);
    }
    void stop(uint8_t why, bool invalidate=true) {
        if((moving() || obstaclePaused) && why!=RL_OK) {
            if(why==RL_LEASE_LOST) lastEvent=ZE_HEARTBEAT_LOST;
            else if(why==RL_BAD_FRAME) lastEvent=ZE_UART_ERROR;
            else if(why==RL_LOCAL_STOP) lastEvent=ZE_LOCAL_STOP;
            else lastEvent=ZE_SESSION_ERROR;
        }
        if(calibrating) calibrated=false; // An interrupted sweep cannot be used.
        following=calibrating=obstaclePaused=reversing=false; reason=why; userRequest=0;
        if(invalidate) { session=sequence=0; lastType=0; }
    }
    void tick(uint32_t now) {
        if(moving() && uint32_t(now-lastLease)>=LEASE_MS) stop(RL_LEASE_LOST);
        // An older supervisor sends regular KEEP packets after its single
        // reverse grant. Preserve its one-second manoeuvre.
        if(reversing && uint32_t(now-lastReverseGrant)>=LEASE_MS) {
            stop(RL_OK,false);
            lastEvent=ZE_REVERSE_DONE;
        }
    }
    bool requestLocal(uint8_t op) {
        if(!session || moving() || userRequest) return false;
        if(op==RL_ZUMO_CALIBRATE) userRequest=RL_USER_ZUMO_CALIBRATE;
        else if(op==RL_START && calibrated) userRequest=RL_USER_START;
        else return false;
        return true;
    }
    void finishCalibration() {
        // Match the original sketch: a completed 80-step sweep is accepted.
        calibrating=false; calibrated=true; reason=RL_OK; lastEvent=ZE_CAL_DONE;
    }
    RlPacket handle(const RlPacket &p, uint32_t now) {
        tick(now); // A late KEEP cannot revive expired motion.
        uint8_t result=RL_OK;
        if(p.arg || p.detail || p.type<RL_HELLO || p.type>RL_ZUMO_REFILLED) {
            stop(RL_BAD_FRAME); result=RL_BAD_COMMAND;
        } else if(p.type==RL_STOP) {
            if(moving()) lastEvent=ZE_MSP_STOP;
            stop(RL_OK); // Session-independent STOP.
        }
        else if(p.type==RL_HELLO && p.session && p.seq==0) {
            if(moving()) lastEvent=ZE_MSP_RESYNC;
            stop(RL_OK); session=p.session; sequence=0; lastType=RL_HELLO;
        } else if(!session || p.session!=session) {
            stop(RL_BAD_SESSION); result=RL_BAD_SESSION;
        } else if(p.seq==sequence && p.type==lastType) {
            result=lastResult; // Duplicate: no repeat action or lease extension.
        } else if(sequence==65535u || p.seq!=uint16_t(sequence+1u)) {
            stop(RL_BAD_SEQUENCE); result=RL_BAD_SEQUENCE;
        } else {
            sequence=p.seq; lastType=p.type;
            switch(p.type) {
            case RL_STATUS: result=reason; break;
            case RL_ZUMO_REFILLED:
                // A late refill message cannot start a parked robot.
                if(!reversing || !calibrated) result=RL_BAD_COMMAND;
                else {
                    reversing=false; following=true; lastLease=now;
                    lastEvent=ZE_FOLLOWING;
                }
                break;
            case RL_ZUMO_REVERSE:
                if(!following && !reversing) result=RL_BAD_COMMAND;
                else {
                    following=false;
                    reversing=true;
                    lastLease=lastReverseGrant=now;
                    lastEvent=ZE_EMPTY_REVERSE;
                }
                break;
            case RL_ZUMO_PAUSE:
                // Only an active line run can pause. Preserve the session so
                // a local STOP or reset invalidates any subsequent START.
                if(!following) result=RL_BAD_COMMAND;
                else {
                    stop(RL_OK,false);
                    obstaclePaused=true; lastEvent=ZE_OBSTACLE_PAUSE;
                }
                break;
            case RL_ZUMO_CALIBRATE:
                userRequest=0;
                if(moving()) result=RL_CAL_BUSY;
                else {
                    obstaclePaused=false; calibrated=false; calibrating=true; reason=RL_OK; lastLease=now;
                    lastEvent=ZE_CALIBRATING;
                }
                break;
            case RL_START:
                userRequest=0;
                if(calibrating || reversing) result=RL_CAL_BUSY;
                else if(!calibrated) result=RL_NOT_CAL;
                else if(!following) {
                    obstaclePaused=false; following=true; reason=RL_OK; lastLease=now; lastEvent=ZE_FOLLOWING;
                }
                break;
            case RL_KEEP:
                if(moving()) lastLease=now;
                else result=reason; // A completed sweep replies OK, stopped.
                break;
            case RL_CLEAR:
                stop(RL_OK,false); calibrated=false; break;
            default:
                stop(RL_BAD_FRAME); result=RL_BAD_COMMAND; break;
            }
            lastResult=result;
        }
        if(p.type==RL_STATUS && userRequest && session && p.session==session &&
           p.seq==sequence && lastType==RL_STATUS && !moving()) result=userRequest;
        RlPacket reply={uint8_t(p.type|RL_REPLY),p.session,p.seq,flags(),result};
        return reply;
    }
private:
    uint8_t lastType=0, lastResult=RL_OK;
};
#endif
