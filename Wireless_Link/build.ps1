param([ValidateSet('Both','Pico','ESP32')][string]$Target = 'Both')
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path $PSScriptRoot -Parent
$python = Join-Path $env:USERPROFILE '.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe'
& $python (Join-Path $PSScriptRoot 'configure.py')
if ($LASTEXITCODE) { throw 'Network configuration failed' }

if ($Target -in @('Both','Pico')) {
    $picoRoot = Join-Path $env:USERPROFILE '.pico-sdk'
    $cmake = Join-Path $picoRoot 'cmake/v4.3.4/bin/cmake.exe'
    $ninja = Join-Path $picoRoot 'ninja/v1.13.2/ninja.exe'
    $sdk = Join-Path $picoRoot 'sdk/2.3.1'
    $toolchain = Join-Path $picoRoot 'toolchain/15_2_Rel1'
    $pioasm = Join-Path $picoRoot 'tools/2.3.1/pioasm'
    $picotool = Join-Path $picoRoot 'picotool/2.3.1/picotool'
    $source = Join-Path $projectRoot 'Pico_Codes/wireless_robot_link'
    $build = Join-Path $source 'build'
    & $cmake -S $source -B $build -G Ninja "-DPICO_SDK_PATH=$sdk" "-DPICO_TOOLCHAIN_PATH=$toolchain" "-DCMAKE_MAKE_PROGRAM=$ninja" "-Dpioasm_DIR=$pioasm" "-Dpicotool_DIR=$picotool" '-DCMAKE_BUILD_TYPE=Release' '-DPICO_NO_PICOTOOL=0'
    if ($LASTEXITCODE) { throw 'Pico CMake configuration failed' }
    & $cmake --build $build --parallel 4
    if ($LASTEXITCODE) { throw 'Pico build failed' }
}
if ($Target -in @('Both','ESP32')) {
    $cli = Join-Path $env:LOCALAPPDATA 'Programs/Arduino IDE/resources/app/lib/backend/resources/arduino-cli.exe'
    & $cli compile --fqbn 'esp32:esp32:firebeetle32' --libraries (Join-Path $PSScriptRoot 'libraries') --build-path (Join-Path $PSScriptRoot 'build/esp32') (Join-Path $projectRoot 'ESP32_Code/laptop_gateway')
    if ($LASTEXITCODE) { throw 'ESP32 build failed; install the official esp32:esp32 core first' }
}
