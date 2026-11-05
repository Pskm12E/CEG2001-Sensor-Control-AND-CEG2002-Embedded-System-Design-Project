$ErrorActionPreference='Stop'
$projectRoot=[System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot '../..'))
$cli=Join-Path $env:USERPROFILE 'AppData/Local/Programs/Arduino IDE/resources/app/lib/backend/resources/arduino-cli.exe'
$settings=Join-Path $env:USERPROFILE '.arduinoIDE/arduino-cli.yaml'
& $cli --config-file $settings compile --jobs 4 --fqbn 'esp32:esp32:XIAO_ESP32S3:PSRAM=opi' --libraries (Join-Path $projectRoot 'Laptop/Tools/Communication/libraries') --build-path (Join-Path $PSScriptRoot 'build/xiao-camera-wifi') (Join-Path $PSScriptRoot 'xiao_camera_wifi')
if($LASTEXITCODE) { throw 'XIAO wireless camera build failed' }
