/* Shared C/C++ UART frame format. MSP430 includes this same header.
 * CRC detects corruption; session/sequence correlate requests, not authentication.
 * One request followed by one reply: suitable for Uno SoftwareSerial.
 */
#ifndef ROBOT_LINK_H
#define ROBOT_LINK_H
#include <stdint.h>
#define RL_SIZE 11u
#define RL_REPLY 0x80u
enum { RL_HELLO=1, RL_STOP, RL_STATUS, RL_WHITE, RL_BLACK, RL_START, RL_KEEP, RL_CLEAR };
enum { RL_OK=0, RL_NOT_CAL, RL_NOT_CENTER, RL_CAL_BUSY, RL_BAD_SESSION,
       RL_BAD_SEQUENCE, RL_BAD_COMMAND, RL_LEASE_LOST, RL_LINE_LOST,
       RL_UNSTABLE, RL_TURN_TIMEOUT, RL_LOCAL_STOP, RL_BAD_FRAME, RL_CAL_UNSTABLE };
enum { RL_CAL=1, RL_LEFT_BLACK=2, RL_RIGHT_BLACK=4, RL_MOVING=8,
       RL_FAULT=16, RL_LEFT_STABLE=32, RL_RIGHT_STABLE=64, RL_CALIBRATING=128 };
typedef struct { uint8_t type; uint16_t session, seq; uint8_t arg, detail; } RlPacket;
typedef struct { uint8_t data[RL_SIZE], used; } RlParser;
static uint16_t rlCrc(const uint8_t *p, uint8_t count) {
    uint16_t crc=0xffffu;
    uint8_t bit;
    while(count--) {
        crc ^= (uint16_t)*p++ << 8;
        for(bit=0;bit<8;++bit) crc=(crc & 0x8000u) ? (uint16_t)((crc<<1)^0x1021u) : (uint16_t)(crc<<1);
    }
    return crc;
}
static void rlEncode(const RlPacket *p, uint8_t *b) {
    uint16_t crc;
    b[0]=0xa5; b[1]=0x5a; b[2]=p->type;
    b[3]=(uint8_t)p->session; b[4]=(uint8_t)(p->session>>8);
    b[5]=(uint8_t)p->seq; b[6]=(uint8_t)(p->seq>>8);
    b[7]=p->arg; b[8]=p->detail;
    crc=rlCrc(b+2,7); b[9]=(uint8_t)crc; b[10]=(uint8_t)(crc>>8);
}
/* Sliding header search survives partial/startup garbage. 1=frame, -1=bad CRC. */
static int rlFeed(RlParser *s, uint8_t byte, RlPacket *p) {
    uint8_t i, keep;
    uint16_t crc;
    if(!s->used) { if(byte==0xa5) s->data[s->used++]=byte; return 0; }
    if(s->used==1 && byte!=0x5a) { s->used=(byte==0xa5)?1:0; return 0; }
    s->data[s->used++]=byte;
    if(s->used<RL_SIZE) return 0;
    crc=rlCrc(s->data+2,7);
    if(s->data[9]!=(uint8_t)crc || s->data[10]!=(uint8_t)(crc>>8)) {
        keep=0;
        for(i=1;i<RL_SIZE-1;++i)
            if(s->data[i]==0xa5 && s->data[i+1]==0x5a) { keep=i; break; }
        if(keep) { for(i=keep;i<RL_SIZE;++i) s->data[i-keep]=s->data[i]; s->used=RL_SIZE-keep; }
        else { s->used=(s->data[RL_SIZE-1]==0xa5)?1:0; s->data[0]=0xa5; }
        return -1;
    }
    p->type=s->data[2]; p->session=(uint16_t)s->data[3]|((uint16_t)s->data[4]<<8);
    p->seq=(uint16_t)s->data[5]|((uint16_t)s->data[6]<<8);
    p->arg=s->data[7]; p->detail=s->data[8]; s->used=0;
    return 1;
}
#endif
