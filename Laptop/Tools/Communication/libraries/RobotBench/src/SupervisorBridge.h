#ifndef SUPERVISOR_BRIDGE_H
#define SUPERVISOR_BRIDGE_H
#include <stdint.h>
#include <stddef.h>

/* C/C++ wire format for diagnostic I2C. No START, pump or calibration opcode.
 * Byte arrays avoid compiler packing/endianness dependencies. CRC is integrity
 * checking, not authentication. STOP is idempotent and means REQUESTED only. */
#define MB_ADDRESS 0x32u
#define MB_REQUEST_SIZE 10u
#define MB_REPLY_SIZE 24u
#define MB_STATUS 1u
#define MB_STOP 2u

static uint16_t mbCrc(const uint8_t *b, size_t n) {
    uint16_t crc=0xffffu; size_t i; uint8_t bit;
    for(i=0;i<n;++i) {
        crc^=(uint16_t)b[i]<<8;
        for(bit=0;bit<8;++bit) crc=(uint16_t)((crc&0x8000u)?(crc<<1)^0x1021u:crc<<1);
    }
    return crc;
}
static uint16_t mbGet16(const uint8_t *b) { return (uint16_t)(b[0]|((uint16_t)b[1]<<8)); }
static uint32_t mbGet32(const uint8_t *b) { return (uint32_t)mbGet16(b)|((uint32_t)mbGet16(b+2)<<16); }
static void mbSet16(uint8_t *b,uint16_t v) { b[0]=(uint8_t)v; b[1]=(uint8_t)(v>>8); }
static void mbSet32(uint8_t *b,uint32_t v) { mbSet16(b,(uint16_t)v); mbSet16(b+2,(uint16_t)(v>>16)); }
static void mbSeal(uint8_t *b,size_t n) { mbSet16(b+n-2,mbCrc(b,n-2)); }
static int mbRequestValid(const uint8_t *b,size_t n) {
    return n==MB_REQUEST_SIZE && b[0]==0xb6u && b[1]==1u &&
        (b[2]==MB_STATUS || b[2]==MB_STOP) && b[3]==0 && mbGet32(b+4)!=0 &&
        mbGet16(b+8)==mbCrc(b,8);
}
static void mbRequest(uint8_t *b,uint8_t op,uint32_t token) {
    b[0]=0xb6u; b[1]=1; b[2]=op; b[3]=0; mbSet32(b+4,token); mbSeal(b,MB_REQUEST_SIZE);
}
static int mbReplyValid(const uint8_t *b,size_t n,uint8_t op,uint32_t token) {
    return n==MB_REPLY_SIZE && b[0]==0xb7u && b[1]==1 && b[2]==op &&
        (op==MB_STATUS || op==MB_STOP) && b[3]==0 && token!=0 && mbGet32(b+4)==token &&
        b[10]<=1 && b[11]<=1 && b[15]==0 && mbGet16(b+22)==mbCrc(b,22);
}
#endif
