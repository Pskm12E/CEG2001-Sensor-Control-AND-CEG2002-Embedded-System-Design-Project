#pragma once
#include "hardware/i2c.h"
#include "SupervisorBridge.h"

// GP4 SDA, GP5 SCL. External pull-ups to 3.3V are required for the wired test.
// Each I2C operation has a 20 ms bound. No requests are replayed on reconnect.
class MspBridge {
    uint8_t op_=0;
    uint32_t token_=0, started_=0, lastRead_=0, lastGood_=0;
    bool busy_=false, good_=false;
    int result_=0; // 0 pending/none, 1 verified reply, -1 unavailable, -2 unknown outcome
    int lastWrite_=-99, lastReadResult_=-99;
    unsigned invalidReplies_=0;
    const char *phase_="NEVER";
public:
    uint8_t reply[MB_REPLY_SIZE]{};
    void init() {
        i2c_init(i2c0, 50000);
        gpio_set_function(4, GPIO_FUNC_I2C); gpio_set_function(5, GPIO_FUNC_I2C);
        gpio_pull_up(4); gpio_pull_up(5); // idle when unplugged; not a substitute for external pull-ups
        token_=time_us_32();
    }
    bool busy() const { return busy_; }
    int lastWrite() const { return lastWrite_; }
    int lastReadResult() const { return lastReadResult_; }
    unsigned invalidReplies() const { return invalidReplies_; }
    const char *phase() const { return phase_; }
    const char *state(uint32_t now) const {
        return good_ ? ((uint32_t)(now-lastGood_)<1500u ? "UP" : "STALE") : "NOT_CONNECTED";
    }
    void cancel() { if(busy_) phase_="CANCELLED"; busy_=false; result_=0; }
    void start(uint8_t op,uint32_t now) {
        op_=op; if(++token_==0) ++token_;
        uint8_t request[MB_REQUEST_SIZE]; mbRequest(request,op_,token_);
        busy_=true; result_=0; started_=lastRead_=now;
        phase_="WRITE"; lastReadResult_=-99; invalidReplies_=0;
        lastWrite_=i2c_write_timeout_us(i2c0,MB_ADDRESS,request,sizeof(request),false,20000);
        if(lastWrite_!=(int)sizeof(request)) {
            busy_=good_=false; result_=op==MB_STOP?-2:-1;
        }
    }
    void service(uint32_t now) {
        if(!busy_) return;
        if((uint32_t)(now-started_)>=600u) { phase_="REPLY_DEADLINE"; busy_=good_=false; result_=op_==MB_STOP?-2:-1; return; }
        if((uint32_t)(now-lastRead_)<15u) return;
        lastRead_=now;
        uint8_t frame[MB_REPLY_SIZE];
        phase_="READ";
        lastReadResult_=i2c_read_timeout_us(i2c0,MB_ADDRESS,frame,sizeof(frame),false,20000);
        if(lastReadResult_!=(int)sizeof(frame)) {
            busy_=good_=false; result_=op_==MB_STOP?-2:-1; return;
        }
        // An old mailbox reply can arrive while the MSP services its Uno UART.
        // Re-read only; never resend a command whose outcome is unknown.
        if(mbReplyValid(frame,sizeof(frame),op_,token_)) {
            phase_="VERIFIED";
            memcpy(reply,frame,sizeof(frame)); busy_=false; good_=true; lastGood_=now; result_=1;
        } else { phase_="VERIFY"; ++invalidReplies_; }
    }
    int takeResult() { int r=result_; result_=0; return r; }
};
