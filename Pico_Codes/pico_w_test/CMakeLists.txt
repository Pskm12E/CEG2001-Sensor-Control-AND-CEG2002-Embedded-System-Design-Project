# == DO NOT EDIT THE FOLLOWING LINES for the Raspberry Pi Pico VS Code Extension to work ==
if(WIN32)
    set(USERHOME $ENV{USERPROFILE})
else()
    set(USERHOME $ENV{HOME})
endif()
set(sdkVersion 2.3.1)
set(toolchainVersion 15_2_Rel1)
set(picotoolVersion 2.3.1)
set(picoVscode ${USERHOME}/.pico-sdk/cmake/pico-vscode.cmake)
if (EXISTS ${picoVscode})
    include(${picoVscode})
endif()
# ====================================================================================
cmake_minimum_required(VERSION 3.13)

# Give VS Code the actual compiler flags and SDK include paths for each source.
set(CMAKE_EXPORT_COMPILE_COMMANDS ON)

# This project is for the RP2040-based Raspberry Pi Pico W in your photos.
set(PICO_BOARD pico_w CACHE STRING "Target board")

# The VS Code Pico extension supplies the SDK and compiler during project import.
include(pico_sdk_import.cmake)

project(pico_w_test C CXX ASM)
set(CMAKE_C_STANDARD 11)
set(CMAKE_CXX_STANDARD 17)
pico_sdk_init()

add_executable(pico_w_test main.cpp)
target_link_libraries(pico_w_test pico_stdlib pico_cyw43_arch_none)

# Send printf messages through the USB cable, without wiring a UART adapter.
pico_enable_stdio_usb(pico_w_test 1)
pico_enable_stdio_uart(pico_w_test 0)
pico_add_extra_outputs(pico_w_test)
