$ErrorActionPreference='Stop'
$projectRoot=[System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot '../../..'))
$python=Join-Path $env:USERPROFILE '.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe'
& $python (Join-Path $PSScriptRoot 'configure.py')
if($LASTEXITCODE) { throw 'Network configuration failed' }
& (Join-Path $projectRoot 'Car/MSP430/build_robot_supervisor.ps1') -EspUart
if($LASTEXITCODE) { throw 'MSP build failed' }
$cli=Join-Path $env:USERPROFILE 'AppData/Local/Programs/Arduino IDE/resources/app/lib/backend/resources/arduino-cli.exe'
& $cli --config-file (Join-Path $env:USERPROFILE '.arduinoIDE/arduino-cli.yaml') compile --fqbn 'esp32:esp32:firebeetle32' --libraries (Join-Path $PSScriptRoot 'libraries') --build-path (Join-Path $PSScriptRoot 'build/esp32-direct') (Join-Path $projectRoot 'Car/ESP32_Gateway/robot_wifi_gateway')
if($LASTEXITCODE) { throw 'Direct ESP32 bridge build failed' }
