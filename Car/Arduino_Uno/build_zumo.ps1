$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot '../../Laptop/Tools/Communication/build_env.ps1')
$cli = Get-RobotArduinoCli
$settings = @(Get-RobotArduinoConfig)
& $cli @settings compile --fqbn 'arduino:avr:uno' --build-path (Join-Path $PSScriptRoot 'build/zumo_line_follow') (Join-Path $PSScriptRoot 'zumo_line_follow')
if ($LASTEXITCODE -ne 0) { throw "Uno build failed (exit $LASTEXITCODE)." }
Write-Host 'Built the Zumo firmware.'
