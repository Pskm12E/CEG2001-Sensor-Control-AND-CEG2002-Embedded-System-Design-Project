/* Robot MSP430F5529 supervisor. MSP is the authority for Uno line following.
 * UART0 P3.3/P3.4: Uno link; default UART1 P4.4/P4.5: USB console.
 * SUPERVISOR_ESP_UART: UART1 remapped P4.1 TX/P4.2 RX, status/STOP bridge.
 * No automatic start, pump, camera or docking behaviour in this stage.
 */
#include <msp430.h>
#include <stdint.h>
#include <string.h>
#include "../../Arduino_Uno/msp_line_follow/robot_link.h"

typedef struct { volatile uint8_t data[128],head,tail,lost; } Ring;
static Ring usbRx,linkRx;
static volatile uint16_t ticks,uartErrors,rxDrops;
static volatile uint8_t stopButton,buttonDown;
static RlParser parser;
static RlPacket pendingPacket;
static uint16_t session=0x430u,sequence,requestAt,lastPoll,lastLinkByte;
static uint8_t pending,linked,running,queued,peerFlags,peerResult;
static uint16_t badFrames;
static char usbLine[32];
static uint8_t usbUsed,usbDiscard;
#ifndef SUPERVISOR_ESP_UART
static void bridgeInit(void);
static void bridgeService(void);
#endif

static void receive(Ring *r,uint8_t b,uint8_t error) {
    uint8_t next=(r->head+1u)&127u;
    if(error) { ++uartErrors; r->lost=1; }
    else if(next==r->tail) { ++rxDrops; r->lost=1; }
    else { r->data[r->head]=b; r->head=next; }
}
static int pop(Ring *r) {
    uint8_t b;
    if(r->head==r->tail) return -1;
    b=r->data[r->tail]; r->tail=(r->tail+1u)&127u; return b;
}
static uint8_t takeLost(Ring *r) {
    uint8_t lost;
    __disable_interrupt(); lost=r->lost; r->lost=0; __enable_interrupt();
    return lost;
}
static uint8_t put(uint8_t link,uint8_t b) {
    uint16_t start=ticks;
    while(!((link?UCA0IFG:UCA1IFG)&UCTXIFG))
        if((uint16_t)(ticks-start)>=3u) return 0;
    if(link) UCA0TXBUF=b; else UCA1TXBUF=b;
    return 1;
}
static void print(const char *s) { while(*s) if(!put(0,(uint8_t)*s++)) return; }
static void number(uint16_t n) {
    char digits[6]; uint8_t used=0;
    do { digits[used++]=(char)('0'+n%10u); n/=10u; } while(n);
    while(used) put(0,(uint8_t)digits[--used]);
}
static void init(void) {
    WDTCTL=WDTPW|WDTHOLD;
    UCSCTL3=SELREF__REFOCLK;
    __bis_SR_register(SCG0); UCSCTL0=0; UCSCTL1=DCORSEL_2;
    UCSCTL2=FLLD_1|31u;
    UCSCTL4=SELA__REFOCLK|SELS__DCOCLKDIV|SELM__DCOCLKDIV;
    UCSCTL5=0; __bic_SR_register(SCG0); __delay_cycles(32768);
    UCSCTL7&=~DCOFFG;
    P1SEL&=~(BIT0|BIT1); P1OUT|=BIT0|BIT1;
    P1DIR=(P1DIR|BIT0)&~BIT1; P1REN|=BIT1; P1IES|=BIT1;
    P1IFG&=~BIT1; P1IE|=BIT1;
    P4SEL&=~BIT7; P4OUT&=~BIT7; P4DIR|=BIT7;
#ifdef SUPERVISOR_ESP_UART
    /* UART1 moves to accessible side-header pins. USB eZ-FET UART is isolated
     * by pin mapping; USB power and Spy-Bi-Wire programming remain available. */
    PMAPKEYID=PMAPKEY;
    P4MAP1=PM_UCA1TXD; P4MAP2=PM_UCA1RXD;
    P4MAP4=PM_NONE; P4MAP5=PM_NONE;
    PMAPKEYID=0;
    P4DIR&=~(BIT1|BIT2|BIT4|BIT5);
    P4REN&=~(BIT1|BIT2|BIT4|BIT5);
    P4SEL=(P4SEL&~(BIT4|BIT5))|BIT1|BIT2;
#else
    P4SEL|=BIT4|BIT5;
#endif
    UCA1CTL1=UCSWRST|UCSSEL__SMCLK; UCA1CTL0=0;
    UCA1BR0=109; UCA1BR1=0; UCA1MCTL=UCBRS_2;
    UCA1CTL1&=~UCSWRST; UCA1IE=UCRXIE;
    P3OUT|=BIT3|BIT4; P3DIR|=BIT3; P3REN|=BIT4; P3SEL|=BIT3|BIT4;
    UCA0CTL1=UCSWRST|UCSSEL__SMCLK; UCA0CTL0=0;
    UCA0BR0=109; UCA0BR1=0; UCA0MCTL=UCBRS_2;
    UCA0CTL1&=~UCSWRST; UCA0IE=UCRXIE;
    /* UART0 remains configured between requests; framed parser resynchronises. */
    TA0CCR0=3277u-1u; TA0CCTL0=CCIE; TA0CTL=TASSEL__ACLK|MC__UP|TACLR;
    TA1CCR0=655u-1u; TA1CCTL0=0; TA1CTL=TASSEL__ACLK|MC__STOP|TACLR;
    queued=RL_HELLO;
#ifndef SUPERVISOR_ESP_UART
    bridgeInit();
#endif
    __enable_interrupt();
}
static void stopRequested(void) {
    running=0; P4OUT&=~BIT7; queued=RL_STOP;
}
static const char *reasonName(uint8_t reason) {
    switch(reason) {
    case RL_OK: return "OK";
    case RL_NOT_CAL: return "NOT_CALIBRATED";
    case RL_NOT_CENTER: return "CENTRE_BOTH_ON_BLACK";
    case RL_CAL_BUSY: return "CALIBRATING";
    case RL_BAD_SESSION: return "SESSION_LOST";
    case RL_BAD_SEQUENCE: return "SEQUENCE_ERROR";
    case RL_BAD_COMMAND: return "BAD_COMMAND";
    case RL_LEASE_LOST: return "HEARTBEAT_LOST";
    case RL_LINE_LOST: return "LINE_LOST";
    case RL_UNSTABLE: return "SENSOR_UNSTABLE";
    case RL_TURN_TIMEOUT: return "TURN_TIMEOUT";
    case RL_LOCAL_STOP: return "LOCAL_STOP";
    case RL_BAD_FRAME: return "FRAME_ERROR";
    case RL_CAL_UNSTABLE: return "CALIBRATION_UNSTABLE";
    default: return "UNKNOWN";
    }
}
static const char *sensorName(uint8_t stable,uint8_t black) {
    if(!linked) return "UNKNOWN";
    if(!(peerFlags&RL_CAL)) return "NC";
    if(!(peerFlags&stable)) return "UNSTABLE";
    return (peerFlags&black)?"BLACK":"WHITE";
}
static void status(void) {
    print("STATUS BOARD=MSP430F5529 FW=SUPERVISOR_V2 LINK=");
    print(linked?"READY":"SYNCING"); print(" RUN="); number(running);
    print(" CAL="); print((peerFlags&RL_CALIBRATING)?"SAMPLING":((peerFlags&RL_CAL)?"READY":"NEEDED"));
    print(" L2="); print(sensorName(RL_LEFT_STABLE,RL_LEFT_BLACK));
    print(" R4="); print(sensorName(RL_RIGHT_STABLE,RL_RIGHT_BLACK));
    print(" LED2="); print(running?"ON":"OFF");
    print(" FLAGS="); number(peerFlags); print(" RESULT="); number(peerResult);
    print(" PENDING="); number(pending?pendingPacket.type:0);
    print(" UART_ERRORS="); number(uartErrors); print(" RX_DROPS="); number(rxDrops);
    print(" BAD_FRAMES="); number(badFrames);
#ifdef SUPERVISOR_ESP_UART
    print(" BRIDGE=ESP_UART_V1\r\n");
#else
    print(" BRIDGE=I2C_V1\r\n");
#endif
}
#ifdef SUPERVISOR_ESP_UART
/* Only status, identity and STOP cross the Wi-Fi bridge in this stage.
 * Positive IDs correlate replies; malformed/overflow IDs never execute. */
static uint8_t netCommand(const char *line) {
    const char *p=line,*idStart; uint32_t id=0; uint8_t digits=0;
    if(strncmp(p,"NET ",4)) return 0;
    p+=4; idStart=p;
    if(*p<'1' || *p>'9') { print("NET ERROR BAD_ID\r\n"); return 1; }
    while(*p>='0' && *p<='9') {
        uint8_t digit=(uint8_t)(*p-'0');
        if(id>429496729u || (id==429496729u && digit>5u)) {
            print("NET ERROR BAD_ID\r\n"); return 1;
        }
        id=id*10u+digit; ++p; ++digits;
    }
    if(*p++!=' ') { print("NET ERROR BAD_ID\r\n"); return 1; }
    print("NET "); while(digits--) put(0,(uint8_t)*idStart++); print(" ");
    if(!strcmp(p,"PING")) print("PONG MSP430 SUPERVISOR_V2 ESP_UART_V1\r\n");
    else if(!strcmp(p,"STATUS")) status();
    else if(!strcmp(p,"STOP")) { stopRequested(); print("STOP REQUESTED\r\n"); }
    else print("ERROR UNSUPPORTED\r\n");
    return 1;
}
#endif
#ifndef SUPERVISOR_ESP_UART
static void help(void) {
    print("ROBOT SUPERVISOR V2 | 9600 baud\r\n");
    print("W: both IR over WHITE; B: both over BLACK; wait for calibration.\r\n");
    print("F: follow (both black); S: stop; C: clear; STATUS: readings.\r\n");
    print("H/LINK: resynchronise stopped; S2: stop. No automatic restart.\r\n");
    print("FLAGS: CAL=1 LBLACK=2 RBLACK=4 FOLLOW=8 FAULT=16 LSTABLE=32 RSTABLE=64 CALIBRATING=128\r\n");
}
#endif
static void command(void) {
#ifndef SUPERVISOR_ESP_UART
    uint8_t op=0;
#endif
    usbLine[usbUsed]=0;
#ifdef SUPERVISOR_ESP_UART
    if(netCommand(usbLine)) return;
    /* The external console is now the ESP transport, not a direct USB console.
     * Reject legacy unframed START/calibration commands on that input. */
    print("ERR USE NET ID PING/STATUS/STOP\r\n"); return;
#else
    if(!strcmp(usbLine,"S") || !strcmp(usbLine,"STOP")) { stopRequested(); print("STOP REQUESTED\r\n"); return; }
    if(!strcmp(usbLine,"PING")) { print("PONG MSP430 SUPERVISOR_V2\r\n"); return; }
    if(!strcmp(usbLine,"STATUS")) { status(); return; }
    if(!strcmp(usbLine,"?") || !strcmp(usbLine,"HELP")) { help(); return; }
    if(!strcmp(usbLine,"H") || !strcmp(usbLine,"LINK")) op=RL_HELLO;
    else if(!strcmp(usbLine,"W")) op=RL_WHITE;
    else if(!strcmp(usbLine,"B")) op=RL_BLACK;
    else if(!strcmp(usbLine,"C")) op=RL_CLEAR;
    else if(!strcmp(usbLine,"F") || !strcmp(usbLine,"START")) op=RL_START;
    if(!op) { print("ERR UNKNOWN COMMAND\r\n"); return; }
    if(queued==RL_STOP) { print("WAIT: stopping\r\n"); return; }
    if(op==RL_START && running) { print("ALREADY FOLLOWING\r\n"); return; }
    if(op!=RL_HELLO && !linked) { print("WAIT: link not ready\r\n"); return; }
    if(queued) { print("BUSY: command already queued\r\n"); return; }
    if(op!=RL_START) { running=0; P4OUT&=~BIT7; }
    queued=op; print("QUEUED "); number(op); print("\r\n");
#endif
}
static void readUsb(void) {
    int c; uint8_t budget=64;
    if(takeLost(&usbRx)) { usbUsed=0; usbDiscard=1; stopRequested(); }
    while(budget-- && (c=pop(&usbRx))>=0) {
        if(c=='\r' || c=='\n') {
            if(usbDiscard) print("ERR INVALID LINE; STOP REQUESTED\r\n");
            else if(usbUsed) command();
            usbUsed=0; usbDiscard=0;
        } else if(!usbDiscard) {
            if(c<32 || c>126 || usbUsed>=sizeof(usbLine)-1) {
                usbUsed=0; usbDiscard=1; stopRequested();
            } else { if(c>='a' && c<='z') c-=32; usbLine[usbUsed++]=(char)c; }
        }
    }
}
static void sendRequest(uint8_t op) {
    uint8_t b[RL_SIZE],i;
    if(op==RL_HELLO) {
        session=(uint16_t)(session+0x101u+ticks); if(!session) session=1;
        sequence=0; running=linked=0; P4OUT&=~BIT7;
    } else {
        if(sequence==65535u && op!=RL_STOP) { stopRequested(); return; }
        ++sequence;
    }
    pendingPacket.type=op; pendingPacket.session=session; pendingPacket.seq=sequence;
    pendingPacket.arg=pendingPacket.detail=0;
    rlEncode(&pendingPacket,b); pending=1; requestAt=lastPoll=ticks;
    for(i=0;i<RL_SIZE;++i) if(!put(1,b[i])) {
        pending=linked=running=0; P4OUT&=~BIT7; queued=RL_STOP;
        print("LINK TRANSMIT FAILED; STOPPING\r\n"); return;
    }
}
static void response(const RlPacket *p) {
    uint8_t op=pendingPacket.type;
    if(!pending || p->type!=(uint8_t)(op|RL_REPLY) ||
       p->session!=pendingPacket.session || p->seq!=pendingPacket.seq) return;
    pending=0; peerFlags=p->arg; peerResult=p->detail;
    if(op==RL_HELLO) linked=(p->detail==RL_OK);
    else if(op==RL_STOP) { linked=running=0; if(!queued) queued=RL_HELLO; }
    else if(op==RL_START) {
        running=p->detail==RL_OK && (p->arg&RL_MOVING) && queued!=RL_STOP;
        print(running?"FOLLOWING; S TO STOP\r\n":"START REFUSED; RESULT=");
        if(!running) { print(reasonName(p->detail)); print("\r\n"); }
    }
    if(p->detail==RL_BAD_SESSION || p->detail==RL_BAD_SEQUENCE ||
       (running && !(p->arg&RL_MOVING))) {
        stopRequested(); linked=0; print("PEER STOPPED/SESSION LOST; NO AUTO RESTART\r\n");
    }
    if(running) P4OUT|=BIT7; else P4OUT&=~BIT7;
    if(op==RL_HELLO) print(linked?"LINK READY; STOPPED\r\n":"LINK SYNC REJECTED\r\n");
    else if(op==RL_STOP) print("STOP CONFIRMED\r\n");
    else if(op==RL_WHITE || op==RL_BLACK || op==RL_CLEAR) {
        print("CALIBRATION COMMAND ACK; FLAGS="); number(peerFlags); print("\r\n");
    }
}
static void serviceLink(void) {
    int c,result; uint8_t budget=64,op; RlPacket p;
    if(takeLost(&linkRx)) { parser.used=0; stopRequested(); linked=0; }
    if(parser.used && (uint16_t)(ticks-lastLinkByte)>=2u) { parser.used=0; ++badFrames; stopRequested(); }
    while(budget-- && (c=pop(&linkRx))>=0) {
        lastLinkByte=ticks; result=rlFeed(&parser,(uint8_t)c,&p);
        if(result<0) { ++badFrames; stopRequested(); }
        else if(result>0) response(&p);
    }
    if(pending && (uint16_t)(ticks-requestAt)>=5u) {
        op=pendingPacket.type; pending=linked=running=0; P4OUT&=~BIT7;
        queued=(op==RL_STOP)?RL_HELLO:RL_STOP;
        print("LINK TIMEOUT; STOPPING; F REQUIRED AFTER RECOVERY\r\n");
    }
    if(pending) return;
    if(queued) { op=queued; queued=0; sendRequest(op); }
    else if(!linked && (uint16_t)(ticks-lastPoll)>=10u) sendRequest(RL_HELLO);
    else if(linked && (uint16_t)(ticks-lastPoll)>=(running?2u:3u))
        sendRequest(running?RL_KEEP:RL_STATUS);
}
#ifndef SUPERVISOR_ESP_UART
#include "supervisor_i2c.h"
#endif
int main(void) {
    init(); print("ROBOT SUPERVISOR V2; STOPPED; TYPE HELP\r\n");
    for(;;) {
#ifndef SUPERVISOR_ESP_UART
        bridgeService();
#endif
        readUsb();
        if(stopButton) { stopButton=0; stopRequested(); print("S2 STOP REQUESTED\r\n"); }
        serviceLink();
        __disable_interrupt();
        if(usbRx.head!=usbRx.tail || linkRx.head!=linkRx.tail || stopButton
#ifndef SUPERVISOR_ESP_UART
           || bridgePending
#endif
        ) __enable_interrupt();
        else __bis_SR_register(LPM0_bits|GIE);
    }
}
#pragma vector=USCI_A1_VECTOR
__interrupt void usb_uart_isr(void) {
    if(UCA1IV==2) { uint8_t err=UCA1STAT&UCRXERR,b=UCA1RXBUF; receive(&usbRx,b,err); __bic_SR_register_on_exit(LPM0_bits); }
}
#pragma vector=USCI_A0_VECTOR
__interrupt void link_uart_isr(void) {
    if(UCA0IV==2) { uint8_t err=UCA0STAT&UCRXERR,b=UCA0RXBUF; receive(&linkRx,b,err); __bic_SR_register_on_exit(LPM0_bits); }
}
#pragma vector=TIMER0_A0_VECTOR
__interrupt void heartbeat_isr(void) {
    static uint8_t step;
    ++ticks; if(++step>=10u) step=0;
    if(step==0u || step==2u) P1OUT|=BIT0; else P1OUT&=~BIT0;
    __bic_SR_register_on_exit(LPM0_bits);
}
#pragma vector=PORT1_VECTOR
__interrupt void button_isr(void) {
    if(P1IFG&BIT1) {
        P1IE&=~BIT1; P1IFG&=~BIT1; buttonDown=0;
        TA1CCTL0=CCIE; TA1CTL=TASSEL__ACLK|MC__UP|TACLR;
        stopButton=1; __bic_SR_register_on_exit(LPM0_bits); // stop on first falling edge
    }
}
#pragma vector=TIMER1_A0_VECTOR
__interrupt void button_release_isr(void) {
    if(P1IN&BIT1) {
        if(++buttonDown>=2u) { TA1CCTL0=0; TA1CTL=TASSEL__ACLK|MC__STOP|TACLR; P1IFG&=~BIT1; P1IE|=BIT1; }
    } else buttonDown=0;
}
