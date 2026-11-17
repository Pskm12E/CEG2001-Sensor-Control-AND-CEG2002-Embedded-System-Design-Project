$ErrorActionPreference = 'Stop'
$taskCli = Join-Path $env:LOCALAPPDATA 'Programs/Arduino IDE/resources/app/lib/backend/resources/arduino-cli.exe'
$taskConfig = Join-Path $env:USERPROFILE '.arduinoIDE/arduino-cli.yaml'
$taskProtocol = Join-Path $PSScriptRoot 'msp_line_follow/robot_link.h'
$taskBundledProtocol = Join-Path $PSScriptRoot 'zumo_line_follow/robot_link.h'
if((Get-FileHash -LiteralPath $taskProtocol).Hash -ne (Get-FileHash -LiteralPath $taskBundledProtocol).Hash) {
    throw 'Zumo bundled robot_link.h differs from the MSP shared header. Synchronise them before building.'
}
& $taskCli --config-file $taskConfig compile --fqbn 'arduino:avr:uno' `
    --build-path (Join-Path $PSScriptRoot 'build/zumo_line_follow') `
    (Join-Path $PSScriptRoot 'zumo_line_follow')
if($LASTEXITCODE -ne 0) { throw "Zumo Uno build failed: $LASTEXITCODE" }
Write-Host 'Built Zumo Uno firmware (not uploaded). Requires Pololu ZumoShield library.'
