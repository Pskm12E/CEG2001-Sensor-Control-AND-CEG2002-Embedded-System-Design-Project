#ifndef ROBOT_CONTROL_H
#define ROBOT_CONTROL_H
#include <stdint.h>
#include "robot_link.h"

/* No hardware dependencies: the exact navigation/lease code is also host-tested. */
enum DriveAction { DRIVE_STOP, DRIVE_FORWARD, DRIVE_LEFT, DRIVE_RIGHT };
struct LineSensor {
    int8_t white=-1, black=-1;
    uint8_t raw=0, candidate=0, stable=0;
    uint32_t since=0;
    bool settled=false;
    bool calibrated() const { return white>=0 && black>=0 && white!=black; }
    bool isBlack() const { return calibrated() && settled && stable==black; }
    void sample(uint8_t value, uint32_t now) {
        raw=value;
        if(value!=candidate) { candidate=value; since=now; settled=false; }
        else if(uint32_t(now-since)>=8) { stable=value; settled=true; }
    }
};
class RobotControl {
public:
    static const uint32_t LEASE_MS=1000;
    LineSensor sensors[2];
    bool following=false;
    DriveAction action=DRIVE_STOP;
    uint8_t reason=RL_OK, calibration=0;
    uint16_t session=0, sequence=0;
    uint32_t lastLease=0;

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
        if(invalidate) { session=0; sequence=0; lastType=0; }
    }
    void tick(uint32_t now, uint8_t left, uint8_t right) {
        sensors[0].sample(left,now); sensors[1].sample(right,now);
        /* Enforce expiry before processing any newly arrived command. */
        if(following && uint32_t(now-lastLease)>=LEASE_MS) stop(RL_LEASE_LOST);
        if(calibration && uint32_t(now-lastSample)>=5) {
            lastSample=now; ++sampleCount;
            highs[0]+=left; highs[1]+=right;
            if(sampleCount==40) {
                bool good=true;
                for(uint8_t i=0;i<2;++i) {
                    int8_t value=-1;
                    if(highs[i]<=2) value=0;
                    else if(highs[i]>=38) value=1;
                    else good=false;
                    if(calibration==RL_WHITE) sensors[i].white=value;
                    else sensors[i].black=value;
                    sensors[i].settled=false; sensors[i].since=now;
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
        if(l && r) { losing=turning=false; action=DRIVE_FORWARD; }
        else if(l || r) {
            losing=false;
            if(!turning) { turning=true; turnSince=now; }
            if(uint32_t(now-turnSince)>=750) { stop(RL_TURN_TIMEOUT); return; }
            action=l?DRIVE_LEFT:DRIVE_RIGHT; lastTurn=action; lastTurnSeen=now;
        } else {
            if(!losing) { losing=true; lossSince=now; }
            if(lastTurn==DRIVE_STOP || uint32_t(now-lossSince)>=250 ||
               uint32_t(now-lastTurnSeen)>=250 || (turning && uint32_t(now-turnSince)>=750))
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
            switch(p.type) {
            case RL_STATUS: result=reason; break;
            case RL_WHITE: case RL_BLACK:
                stop(RL_OK,false); calibration=p.type; sampleCount=highs[0]=highs[1]=0;
                lastSample=now;
                for(uint8_t i=0;i<2;++i) {
                    if(p.type==RL_WHITE) sensors[i].white=-1; else sensors[i].black=-1;
                }
                break;
            case RL_CLEAR:
                stop(RL_OK,false);
                for(uint8_t i=0;i<2;++i) sensors[i].white=sensors[i].black=-1;
                break;
            case RL_START:
                if(calibration) result=RL_CAL_BUSY;
                else if(!calibrated()) result=RL_NOT_CAL;
                else if(!sensors[0].isBlack() || !sensors[1].isBlack()) result=RL_NOT_CENTER;
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
        RlPacket reply={uint8_t(p.type|RL_REPLY),p.session,p.seq,flags(),result};
        return reply;
    }
private:
    bool losing=false, turning=false, uncertain=false;
    DriveAction lastTurn=DRIVE_STOP;
    uint32_t lossSince=0, turnSince=0, uncertainSince=0, lastTurnSeen=0, lastSample=0;
    uint8_t sampleCount=0, highs[2]={0,0}, lastType=0, lastResult=RL_OK;
};
#endif
