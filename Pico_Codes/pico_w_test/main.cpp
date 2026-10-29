#include <cstdio>

#include "pico/stdlib.h"
#include "pico/cyw43_arch.h"

// First connection test for the Raspberry Pi Pico W.
// The onboard LED is connected to its wireless chip, not to GP25.
int main() {
    stdio_init_all();

    if (cyw43_arch_init() != 0) {
        // Repeat the error so it is visible even if the serial monitor opens late.
        while (true) {
            printf("ERROR: Pico W LED driver could not start.\n");
            sleep_ms(1000);
        }
    }

    unsigned long heartbeat = 0;
    while (true) {
        cyw43_arch_gpio_put(CYW43_WL_GPIO_LED_PIN, true);
        printf("Pico W connected | heartbeat %lu | LED ON\n", heartbeat++);
        sleep_ms(500);

        cyw43_arch_gpio_put(CYW43_WL_GPIO_LED_PIN, false);
        sleep_ms(500);
    }
}
