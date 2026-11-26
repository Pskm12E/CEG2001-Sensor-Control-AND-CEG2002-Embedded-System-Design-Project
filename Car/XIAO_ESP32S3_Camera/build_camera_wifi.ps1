$ErrorActionPreference='Stop'
$projectRoot=[System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot '../..'))
. (Join-Path $projectRoot 'Laptop/Tools/Communication/build_env.ps1')
$cli=Get-RobotArduinoCli
$settings=@(Get-RobotArduinoConfig)
& $cli @settings compile --jobs 4 --fqbn 'esp32:esp32:XIAO_ESP32S3:PSRAM=opi' --libraries (Join-Path $projectRoot 'Laptop/Tools/Communication/libraries') --build-path (Join-Path $PSScriptRoot 'build/xiao-camera-wifi') (Join-Path $PSScriptRoot 'xiao_camera_wifi')
if($LASTEXITCODE) { throw 'XIAO wireless camera build failed' }
