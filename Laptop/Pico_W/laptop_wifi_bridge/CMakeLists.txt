cmake_minimum_required(VERSION 3.13)
set(PICO_BOARD pico_w CACHE STRING "RP2040 Raspberry Pi Pico W")
include(../cmake/pico_sdk_import.cmake)
project(laptop_wifi_bridge C CXX ASM)
set(CMAKE_C_STANDARD 11)
set(CMAKE_CXX_STANDARD 17)
pico_sdk_init()
add_executable(laptop_wifi_bridge main.cpp)
target_include_directories(laptop_wifi_bridge PRIVATE
    ${CMAKE_CURRENT_LIST_DIR}
    ${CMAKE_CURRENT_LIST_DIR}/../../Tools/Communication/libraries/RobotBench/src
    ${CMAKE_CURRENT_LIST_DIR}/../../../Car/ESP32_Gateway/robot_wifi_gateway)
target_link_libraries(laptop_wifi_bridge pico_stdlib pico_cyw43_arch_lwip_poll)
target_compile_options(laptop_wifi_bridge PRIVATE -Wall -Wextra)
pico_enable_stdio_usb(laptop_wifi_bridge 1)
pico_enable_stdio_uart(laptop_wifi_bridge 0)
pico_add_extra_outputs(laptop_wifi_bridge)
