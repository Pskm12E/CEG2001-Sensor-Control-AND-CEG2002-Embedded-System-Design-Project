#include <cstdio>
#include <cstring>
#include "pico/stdlib.h"
#include "pico/cyw43_arch.h"
#include "lwip/tcp.h"
#include "RobotBench.h"
#include "NetworkConfig.h"

// No external GPIO, motor, pump, UART or MSP430 job control is initialized here.
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
    if (connected) printf("LINK DOWN; LED OFF; MSP_LINK=NOT_CONNECTED\n");
    connected = ready = closeRequested = false;
    lastId = 0;
    networkLine.reset();
    setLed(false);
    lastTcpAttempt = nowMs();
}

static bool sendLine(const char *line) {
    if (!connection) return false;
    char output[192];
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
        printf("LINK UP: ESP32_GATEWAY; MSP_LINK=NOT_CONNECTED\n");
        return;
    }
    uint32_t id = 0;
    const char *command = nullptr;
    if (!bench::frame(line, "REQ ", id, command) || id <= lastId || !bench::allowed(command)) {
        closeRequested = true;
        return;
    }
    lastId = id;
    lastRequest = nowMs();
    lastNetworkProgress = lastRequest;
    char payload[128];
    if (bench::equal(command, "PING")) snprintf(payload, sizeof(payload), "PONG PICO_W");
    else if (bench::equal(command, "STATUS"))
        snprintf(payload, sizeof(payload), "STATUS BOARD=PICO_W LED=%s MSP_LINK=NOT_CONNECTED BENCH_ONLY", led ? "ON" : "OFF");
    else {
        setLed(bench::equal(command, "LED ON"));
        snprintf(payload, sizeof(payload), "LED=%s", led ? "ON" : "OFF");
        printf("REMOTE %s\n", payload);
    }
    char output[192];
    snprintf(output, sizeof(output), "ACK %lu %s", static_cast<unsigned long>(id), payload);
    if (!sendLine(output)) closeRequested = true;
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
    else if (bench::equal(line, "STATUS"))
        printf("STATUS BOARD=PICO_W GATEWAY_LINK=%s LED=%s WIFI=%d TCP=%s MSP_LINK=NOT_CONNECTED BENCH_ONLY\n",
               ready ? "UP" : "DOWN", led ? "ON" : "OFF",
               cyw43_tcpip_link_status(&cyw43_state, CYW43_ITF_STA),
               connected ? "CONNECTED" : connection ? "CONNECTING" : "DOWN");
    else if (bench::equal(line, "HELP") || bench::equal(line, "?"))
        printf("PING | STATUS | HELP. Remote LED commands go through the ESP32 USB console.\n");
    else printf("ERROR unknown USB command; send HELP\n");
}

int main() {
    stdio_init_all();
    if (cyw43_arch_init()) {
        while (true) { printf("ERROR Pico W wireless initialization failed\n"); sleep_ms(1000); }
    }
    cyw43_arch_enable_sta_mode();
    // USB-powered bench use: keep the radio awake for predictable request latency.
    // Revisit power consumption when the robot's battery design is confirmed.
    if (cyw43_wifi_pm(&cyw43_state, CYW43_NONE_PM))
        printf("WARNING could not disable Wi-Fi power saving\n");
    setLed(false);
    printf("Pico W robot wireless link v1 - onboard LED bench test only\n");
    while (true) {
        cyw43_arch_poll();
        if (closeRequested) disconnect();
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
