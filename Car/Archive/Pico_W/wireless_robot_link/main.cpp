#include <cstdio>
#include <cstring>
#include "pico/stdlib.h"
#include "pico/cyw43_arch.h"
#include "lwip/tcp.h"
#include "RobotBench.h"
#include "NetworkConfig.h"
#include "msp_bridge.h"

// I2C diagnostics/STOP to MSP only; no motor, pump or job decision outputs.
static MspBridge msp;
static uint32_t mspRequestId=0;
static bool mspStopRequest=false;
static bool mspStarted=false;
static tcp_pcb *connection = nullptr;
static bench::Line<128> networkLine;
static bench::Line<64> usbLine;
static bool connected = false, ready = false, closeRequested = false, led = false;
static uint32_t connectedAt = 0, lastRequest = 0, lastId = 0;
static uint32_t lastNetworkProgress = 0;
static uint32_t lastWifiAttempt = 0, lastTcpAttempt = 0;
static bool wifiAttempted = false, tcpAttempted = false;

static uint32_t nowMs() { return to_ms_since_boot(get_absolute_time()); }
static void setLed(bool on) {
    led = on;
    cyw43_arch_gpio_put(CYW43_WL_GPIO_LED_PIN, on);
}

// Called from the main loop only, never from a raw-TCP callback.
static void disconnect() {
    if (connection) {
        tcp_arg(connection, nullptr);
        tcp_recv(connection, nullptr);
        tcp_err(connection, nullptr);
        tcp_abort(connection);
        connection = nullptr;
    }
    if (connected) printf("LINK DOWN; LED OFF; pending requests not replayed\n");
    msp.cancel(); mspRequestId=0; mspStarted=false;
    connected = ready = closeRequested = false;
    lastId = 0;
    networkLine.reset();
    setLed(false);
    lastTcpAttempt = nowMs();
}

static bool sendLine(const char *line) {
    if (!connection) return false;
    char output[256];
    const int n = snprintf(output, sizeof(output), "%s\n", line);
    if (n <= 0 || n >= static_cast<int>(sizeof(output))) return false;
    if (tcp_write(connection, output, static_cast<u16_t>(n), TCP_WRITE_FLAG_COPY) != ERR_OK)
        return false;
    const err_t result = tcp_output(connection);
    return result == ERR_OK;
}

static void handleNetworkLine(const char *line) {
    if (!ready) {
        if (!bench::equal(line, bench::WELCOME)) { closeRequested = true; return; }
        ready = true;
        lastRequest = nowMs();
        lastNetworkProgress = lastRequest;
        printf("LINK UP: ESP32_GATEWAY; bridge diagnostics available\n");
        return;
    }
    uint32_t id = 0;
    const char *command = nullptr;
    if (!bench::frame(line, "REQ ", id, command) || id <= lastId || !bench::allowed(command) || mspRequestId) {
        closeRequested = true;
        return;
    }
    lastId = id;
    lastRequest = nowMs();
    lastNetworkProgress = lastRequest;
    if(bench::equal(command,"MSP STATUS") || bench::equal(command,"MSP STOP")) {
        mspRequestId=id; mspStopRequest=bench::equal(command,"MSP STOP");
        // Start the bounded I2C transaction in the main loop, outside lwIP callbacks.
        return;
    }
    char payload[128];
    if (bench::equal(command, "PING")) snprintf(payload, sizeof(payload), "PONG PICO_W");
    else if (bench::equal(command, "STATUS"))
        snprintf(payload, sizeof(payload), "STATUS BOARD=PICO_W LED=%s MSP_LINK=%s FW=BRIDGE2", led ? "ON" : "OFF", msp.state(nowMs()));
    else {
        setLed(bench::equal(command, "LED ON"));
        snprintf(payload, sizeof(payload), "LED=%s", led ? "ON" : "OFF");
        printf("REMOTE %s\n", payload);
    }
    char output[192];
    snprintf(output, sizeof(output), "ACK %lu %s", static_cast<unsigned long>(id), payload);
    if (!sendLine(output)) closeRequested = true;
}

static void serviceMsp() {
    if(!mspRequestId) return;
    if(!mspStarted) {
        mspStarted=true;
        msp.start(mspStopRequest?MB_STOP:MB_STATUS,nowMs());
    }
    msp.service(nowMs());
    const int result=msp.takeResult();
    if(!result) return;
    char payload[224], output[256];
    if(result<0) snprintf(payload,sizeof(payload),"MSP ERROR %s",result==-2?"STOP_OUTCOME_UNKNOWN":"NOT_CONNECTED");
    else {
        const uint8_t *r=msp.reply;
        snprintf(payload,sizeof(payload),
            "MSP %s BOARD=MSP430F5529 FW=SUPERVISOR_V2 LINK=%s RUN=%u FLAGS=%u RESULT=%u PENDING=%u TICKS=%u UART_ERRORS=%u RX_DROPS=%u BAD_FRAMES=%u",
            mspStopRequest?"STOP=REQUESTED":"STATUS",r[10]?"READY":"SYNCING",r[11],r[12],r[13],r[14],
            mbGet16(r+8),mbGet16(r+16),mbGet16(r+18),mbGet16(r+20));
    }
    snprintf(output,sizeof(output),"ACK %lu %s",static_cast<unsigned long>(mspRequestId),payload);
    mspRequestId=0; mspStarted=false;
    if(!sendLine(output)) closeRequested=true;
}

static err_t onReceive(void *, tcp_pcb *pcb, pbuf *p, err_t error) {
    if (!p) { closeRequested = true; return ERR_OK; }
    if (error != ERR_OK) { pbuf_free(p); closeRequested = true; return ERR_OK; }
    tcp_recved(pcb, p->tot_len);
    for (pbuf *part = p; part && !closeRequested; part = part->next) {
        const auto *bytes = static_cast<const uint8_t *>(part->payload);
        for (u16_t i = 0; i < part->len && !closeRequested; ++i) {
            const auto result = networkLine.push(bytes[i]);
            if (result == bench::Feed::Ready) handleNetworkLine(networkLine.text);
            else if (result == bench::Feed::Invalid) closeRequested = true;
            if (result != bench::Feed::Pending) networkLine.reset();
        }
    }
    pbuf_free(p);
    return ERR_OK;
}
static void onError(void *, err_t error) {
    // lwIP already freed this PCB. The main loop clears application state.
    connection = nullptr;
    closeRequested = true;
    printf("TCP error %d\n", static_cast<int>(error));
}
static err_t onConnect(void *, tcp_pcb *, err_t error) {
    if (error != ERR_OK) { closeRequested = true; return ERR_OK; }
    connected = true;
    connectedAt = nowMs();
    if (!sendLine(bench::HELLO)) closeRequested = true;
    return ERR_OK;
}
static void startTcp() {
    lastTcpAttempt = nowMs();
    tcpAttempted = true;
    ip_addr_t gateway;
    if (!ipaddr_aton("192.168.4.1", &gateway)) return;
    connection = tcp_new_ip_type(IPADDR_TYPE_V4);
    if (!connection) return;
    connectedAt = nowMs();
    tcp_recv(connection, onReceive);
    tcp_err(connection, onError);
    tcp_nagle_disable(connection);
    if (tcp_connect(connection, &gateway, bench::PORT, onConnect) != ERR_OK)
        closeRequested = true;
}
static void usbCommand(const char *line) {
    if (bench::equal(line, "PING")) printf("PONG PICO_W_USB\n");
    else if (bench::equal(line, "I2CDIAG")) {
        // Observation only: does not issue I2C traffic, reset pins or queue commands.
        const i2c_hw_t *hw=i2c_get_hw(i2c0);
        printf("I2CDIAG ADDR=0x32 SDA_GP=4 SCL_GP=5 SDA=%u SCL=%u SDA_FUNC=%u SCL_FUNC=%u PHASE=%s WRITE=%d READ=%d BAD_REPLY=%u BUSY=%u HW_STATUS=0x%lx HW_RAW=0x%lx ABORT=0x%lx TX_FIFO=%lu RX_FIFO=%lu ENABLE=0x%lx\n",
               static_cast<unsigned>(gpio_get(4)),static_cast<unsigned>(gpio_get(5)),
               static_cast<unsigned>(gpio_get_function(4)),static_cast<unsigned>(gpio_get_function(5)),
               msp.phase(),msp.lastWrite(),msp.lastReadResult(),msp.invalidReplies(),static_cast<unsigned>(msp.busy()),
               static_cast<unsigned long>(hw->status),static_cast<unsigned long>(hw->raw_intr_stat),
               static_cast<unsigned long>(hw->tx_abrt_source),static_cast<unsigned long>(hw->txflr),
               static_cast<unsigned long>(hw->rxflr),static_cast<unsigned long>(hw->enable_status));
    }
    else if (bench::equal(line, "STATUS"))
        printf("STATUS BOARD=PICO_W GATEWAY_LINK=%s LED=%s WIFI=%d TCP=%s MSP_LINK=%s FW=BRIDGE2\n",
               ready ? "UP" : "DOWN", led ? "ON" : "OFF",
               cyw43_tcpip_link_status(&cyw43_state, CYW43_ITF_STA),
               connected ? "CONNECTED" : connection ? "CONNECTING" : "DOWN",msp.state(nowMs()));
    else if (bench::equal(line, "HELP") || bench::equal(line, "?"))
        printf("PING | STATUS | I2CDIAG | HELP. I2CDIAG observes the last transaction only. Remote commands use the ESP32 USB console.\n");
    else printf("ERROR unknown USB command; send HELP\n");
}

int main() {
    stdio_init_all();
    msp.init();
    if (cyw43_arch_init()) {
        while (true) { printf("ERROR Pico W wireless initialization failed\n"); sleep_ms(1000); }
    }
    cyw43_arch_enable_sta_mode();
    // USB-powered bench use: keep the radio awake for predictable request latency.
    // Revisit power consumption when the robot's battery design is confirmed.
    if (cyw43_wifi_pm(&cyw43_state, CYW43_NONE_PM))
        printf("WARNING could not disable Wi-Fi power saving\n");
    setLed(false);
    printf("Pico W BRIDGE2 - MSP I2C GP4/GP5; diagnostics and stop requests only\n");
    while (true) {
        cyw43_arch_poll();
        if (closeRequested) disconnect();
        if(ready) serviceMsp();
        const uint32_t now = nowMs();
        int wifi = cyw43_tcpip_link_status(&cyw43_state, CYW43_ITF_STA);
        // An AP reboot can leave the station reporting UP with a stale association.
        // TCP retries alone did not recover in the hardware restart test. Renew
        // association and DHCP after 15 s without a working protocol session.
        if (!ready && wifi == CYW43_LINK_UP && bench::expired(now, lastNetworkProgress, 15000)) {
            disconnect();
            cyw43_arch_disable_sta_mode();
            cyw43_arch_enable_sta_mode();
            cyw43_wifi_pm(&cyw43_state, CYW43_NONE_PM);
            wifiAttempted = tcpAttempted = false;
            lastNetworkProgress = nowMs();
            wifi = cyw43_tcpip_link_status(&cyw43_state, CYW43_ITF_STA);
            printf("Wi-Fi: renewing association after gateway loss\n");
        }
        if (wifi != CYW43_LINK_UP) {
            if (connection || connected) disconnect();
            if (!wifiAttempted || bench::expired(now, lastWifiAttempt, 15000)) {
                wifiAttempted = true;
                lastWifiAttempt = now;
                printf("Wi-Fi: looking for the ESP32 bench gateway\n");
                if (cyw43_arch_wifi_connect_async(BENCH_SSID, BENCH_PASSWORD, CYW43_AUTH_WPA2_AES_PSK))
                    printf("Wi-Fi connection request failed; will retry\n");
            }
        } else if (!connection && (!tcpAttempted || bench::expired(now, lastTcpAttempt, 2000))) startTcp();

        const uint32_t timeoutNow = nowMs();
        if (connection && !ready && bench::expired(timeoutNow, connectedAt, bench::LINK_TIMEOUT_MS)) disconnect();
        if (ready && bench::expired(timeoutNow, lastRequest, bench::LINK_TIMEOUT_MS)) disconnect();

        for (unsigned count = 0; count < 128; ++count) {
            const int c = getchar_timeout_us(0);
            if (c == PICO_ERROR_TIMEOUT) break;
            const auto result = usbLine.push(static_cast<uint8_t>(c));
            if (result == bench::Feed::Ready) usbCommand(usbLine.text);
            else if (result == bench::Feed::Invalid) printf("ERROR invalid or oversized USB line\n");
            if (result != bench::Feed::Pending) usbLine.reset();
        }
        sleep_ms(1);
    }
}
