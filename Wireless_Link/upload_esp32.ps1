param([Parameter(Mandatory=$true)][ValidatePattern('^COM[0-9]+$')][string]$Port)
$ErrorActionPreference = 'Stop'
$device = Get-PnpDevice -Class Ports -PresentOnly | Where-Object {
    $_.FriendlyName -match "\($Port\)$" -and $_.InstanceId -match 'VID_1A86&PID_7523'
}
if (@($device).Count -ne 1) { throw "Expected CH340 ESP32 connection on $Port; no upload attempted" }
$esptool = Join-Path $env:LOCALAPPDATA 'Arduino15/packages/esp32/tools/esptool_py/5.3.1/esptool.exe'
$build = Join-Path $PSScriptRoot 'build/esp32'
$boot = Join-Path $build 'laptop_gateway.ino.bootloader.bin'
$partitions = Join-Path $build 'laptop_gateway.ino.partitions.bin'
$bootApp = Join-Path $build 'boot_app0.bin'
$app = Join-Path $build 'laptop_gateway.ino.bin'
foreach ($file in @($boot,$partitions,$bootApp,$app)) {
    if (-not (Test-Path -LiteralPath $file)) { throw "Build first; missing $file" }
}
# ROM loader uses smaller blocks than the stub. Uncompressed upload recovered
# the observed bad-data-length transfer failure on this USB connection.
& $esptool --chip esp32 --port $Port --baud 115200 --no-stub write-flash --no-compress --flash-mode dio --flash-freq 80m --flash-size 4MB 0x1000 $boot 0x8000 $partitions 0xe000 $bootApp 0x10000 $app
if ($LASTEXITCODE) { throw 'ESP32 upload failed; inspect the error before retrying' }
