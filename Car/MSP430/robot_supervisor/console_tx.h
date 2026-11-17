/* Single main-loop producer / UART ISR consumer; 16-bit indices are atomic on MSP430. */
#ifndef CONSOLE_TX_H
#define CONSOLE_TX_H
#include <stdint.h>
typedef struct { volatile uint8_t data[512]; volatile uint16_t head,tail; } ConsoleTx;
static uint8_t consoleTxPush(ConsoleTx *q,uint8_t byte) {
    uint16_t next=(q->head+1u)&511u;
    if(next==q->tail) return 0;
    q->data[q->head]=byte; q->head=next; return 1;
}
static int consoleTxPop(ConsoleTx *q) {
    uint8_t byte;
    if(q->head==q->tail) return -1;
    byte=q->data[q->tail]; q->tail=(q->tail+1u)&511u; return byte;
}
#endif
