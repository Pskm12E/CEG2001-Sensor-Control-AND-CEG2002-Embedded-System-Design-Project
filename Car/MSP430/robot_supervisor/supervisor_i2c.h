/* USCI_B0 I2C peripheral at 0x32. P3.0 SDA / P3.1 SCL, 3.3V only.
 * Separate from both existing UARTs. Main loop validates/executes commands;
 * ISR only moves bounded buffers. No movement-start opcode exists. */
#include "../../../Laptop/Tools/Communication/libraries/RobotBench/src/SupervisorBridge.h"
static volatile uint8_t bridgeRx[MB_REQUEST_SIZE],bridgeMailbox[MB_REQUEST_SIZE];
static volatile uint8_t bridgeRxUsed,bridgeOverflow,bridgePending,bridgeReceiving;
static volatile uint8_t bridgeReply[MB_REPLY_SIZE],bridgeTx[MB_REPLY_SIZE],bridgeTxUsed;
static volatile uint16_t bridgeRejected;

static void bridgeInit(void) {
    P3REN&=~(BIT0|BIT1); P3SEL|=BIT0|BIT1;
    UCB0CTL1=UCSWRST;
    UCB0CTL0=UCMODE_3|UCSYNC; // addressed peripheral, not I2C controller
    UCB0I2COA=MB_ADDRESS;
    UCB0CTL1&=~UCSWRST;
    UCB0IE=UCSTTIE|UCSTPIE|UCRXIE|UCTXIE;
}
static void bridgeService(void) {
    uint8_t request[MB_REQUEST_SIZE],reply[MB_REPLY_SIZE],i;
    if(!bridgePending) return;
    __disable_interrupt();
    for(i=0;i<MB_REQUEST_SIZE;++i) request[i]=bridgeMailbox[i];
    bridgePending=0; __enable_interrupt();
    if(!mbRequestValid(request,MB_REQUEST_SIZE)) { ++bridgeRejected; return; }
    if(request[2]==MB_STOP) stopRequested();
    memset(reply,0,sizeof(reply));
    reply[0]=0xb7u; reply[1]=1; reply[2]=request[2];
    for(i=4;i<8;++i) reply[i]=request[i];
    mbSet16(reply+8,ticks); reply[10]=linked; reply[11]=running;
    reply[12]=peerFlags; reply[13]=peerResult;
    reply[14]=queued?queued:(pending?pendingPacket.type:0);
    mbSet16(reply+16,uartErrors); mbSet16(reply+18,rxDrops); mbSet16(reply+20,badFrames);
    mbSeal(reply,MB_REPLY_SIZE);
    __disable_interrupt();
    for(i=0;i<MB_REPLY_SIZE;++i) bridgeReply[i]=reply[i];
    __enable_interrupt();
}
static void bridgeReceiveByte(void) {
    uint8_t b=UCB0RXBUF;
    if(bridgeRxUsed<MB_REQUEST_SIZE) bridgeRx[bridgeRxUsed++]=b;
    else bridgeOverflow=1;
}
static void bridgeFinishReceive(void) {
    uint8_t i;
    if(!bridgeReceiving) return;
    // STOP/START have higher interrupt priority than RX: consume a final byte.
    if(UCB0IFG&UCRXIFG) bridgeReceiveByte();
    if(!bridgeOverflow && bridgeRxUsed==MB_REQUEST_SIZE && !bridgePending) {
        for(i=0;i<MB_REQUEST_SIZE;++i) bridgeMailbox[i]=bridgeRx[i];
        bridgePending=1;
    } else if(bridgeRxUsed || bridgeOverflow) ++bridgeRejected;
    bridgeReceiving=bridgeRxUsed=bridgeOverflow=0;
}
#pragma vector=USCI_B0_VECTOR
__interrupt void bridge_i2c_isr(void) {
    uint8_t i;
    switch(UCB0IV) {
    case 6: // START or repeated START
        bridgeFinishReceive();
        bridgeTxUsed=0;
        if(UCB0CTL1&UCTR) {
            // Snapshot makes a multi-byte read consistent if main publishes later.
            for(i=0;i<MB_REPLY_SIZE;++i) bridgeTx[i]=bridgeReply[i];
        } else bridgeReceiving=1;
        break;
    case 8: bridgeFinishReceive(); break; // STOP
    case 10: bridgeReceiveByte(); break;
    case 12: UCB0TXBUF=bridgeTxUsed<MB_REPLY_SIZE?bridgeTx[bridgeTxUsed++]:0xffu; break;
    default: break;
    }
    __bic_SR_register_on_exit(LPM0_bits);
}
