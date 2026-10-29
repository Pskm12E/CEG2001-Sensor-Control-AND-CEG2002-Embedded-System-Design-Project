#include <cstdio>

#include "pico/stdlib.h"
#include "pico/stdio_usb.h"
#include "hardware/clocks.h"
#include "hardware/pwm.h"
#include "forward_test.h"

// Verify these connections, the L298N jumpers and motor supply before uploading.
constexpr uint LEFT_IN1 = 6;
constexpr uint LEFT_IN2 = 7;
constexpr uint LEFT_ENABLE = 8;
constexpr uint RIGHT_IN1 = 9;
constexpr uint RIGHT_IN2 = 10;
constexpr uint RIGHT_ENABLE = 11;
constexpr uint16_t PWM_TOP = 999;
constexpr uint16_t TEST_DUTY = 400; // 40% PWM, not a measured wheel speed.

// Verify wheel direction with the wheels raised. Motor wiring defines forward.
constexpr bool LEFT_FORWARD_IN1_HIGH = true;
constexpr bool RIGHT_FORWARD_IN3_HIGH = true;

void init_low(uint pin) {
    gpio_init(pin);
    gpio_put(pin, false);
    gpio_set_dir(pin, GPIO_OUT);
}

void init_enable(uint pin) {
    init_low(pin);
    const uint slice = pwm_gpio_to_slice_num(pin);
    pwm_config config = pwm_get_default_config();
    pwm_config_set_wrap(&config, PWM_TOP);
    pwm_config_set_clkdiv(&config,
        static_cast<float>(clock_get_hz(clk_sys)) / (2000.0f * (PWM_TOP + 1)));
    pwm_init(slice, &config, false);
    pwm_set_gpio_level(pin, 0);
    gpio_set_function(pin, GPIO_FUNC_PWM);
    pwm_set_enabled(slice, true);
}

void stop_motors() {
    // EN low disables both bridges; the wheels coast rather than actively brake.
    pwm_set_gpio_level(LEFT_ENABLE, 0);
    pwm_set_gpio_level(RIGHT_ENABLE, 0);
    gpio_put(LEFT_IN1, false);
    gpio_put(LEFT_IN2, false);
    gpio_put(RIGHT_IN1, false);
    gpio_put(RIGHT_IN2, false);
}

void drive_forward() {
    gpio_put(LEFT_IN1, LEFT_FORWARD_IN1_HIGH);
    gpio_put(LEFT_IN2, !LEFT_FORWARD_IN1_HIGH);
    gpio_put(RIGHT_IN1, RIGHT_FORWARD_IN3_HIGH);
    gpio_put(RIGHT_IN2, !RIGHT_FORWARD_IN3_HIGH);
    pwm_set_gpio_level(LEFT_ENABLE, TEST_DUTY);
    pwm_set_gpio_level(RIGHT_ENABLE, TEST_DUTY);
}

int main() {
    // Hardware pull-downs on ENA/ENB are still needed during reset/power-up.
    init_enable(LEFT_ENABLE);
    init_enable(RIGHT_ENABLE);
    init_low(LEFT_IN1);
    init_low(LEFT_IN2);
    init_low(RIGHT_IN1);
    init_low(RIGHT_IN2);
    stop_motors();
    stdio_init_all();

    ForwardTest test;
    bool was_connected = false;
    absolute_time_t report_at = get_absolute_time();

    while (true) {
        const bool connected = stdio_usb_connected();
        const int command = getchar_timeout_us(0);
        const bool was_running = test.running();
        test.update(time_us_64() / 1000, connected, command);

        if (was_running && !test.running()) {
            stop_motors();
            // Printing happens after disabling the motors, never during a pulse.
            if (connected) printf("STOPPED: motor outputs disabled.\n");
        } else if (!was_running && test.running()) {
            drive_forward();
        }

        if (connected && !test.running() &&
            (!was_connected || time_reached(report_at))) {
            printf("FORWARD TEST READY | f = forward for 1 second at 40%% PWM | s = stop\n");
            report_at = make_timeout_time_ms(2000);
        }
        was_connected = connected;
        sleep_ms(1);
    }
}
