param([Parameter(Mandatory=$true)][ValidatePattern('^COM[0-9]+$')][string]$Port,
      [ValidateSet('Robot','Desk')][string]$Role='Robot')
$ErrorActionPreference='Stop'
$projectRoot=[System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot '../../..'))
$firmware=Join-Path $projectRoot $(if($Role -eq 'Desk') { 'Laptop/Pico_W/laptop_wifi_bridge/build/laptop_wifi_bridge.uf2' } else { 'Car/Archive/Pico_W/wireless_robot_link/build/wireless_robot_link.uf2' })
if(-not (Test-Path -LiteralPath $firmware)) { throw 'Build the Pico firmware first.' }
$python=Join-Path $env:USERPROFILE '.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe'
$existing=@([System.IO.DriveInfo]::GetDrives() | Where-Object { $_.IsReady -and $_.VolumeLabel -eq 'RPI-RP2' })
if($existing.Count) { throw 'A BOOTSEL drive already exists. Identify it before using this automatic uploader.' }
$resetScript=@'
import sys,time
sys.path.insert(0,sys.argv[2])
import serial
from serial.tools import list_ports
port=sys.argv[1]
p=next((p for p in list_ports.comports() if p.device==port),None)
if not p or (p.vid,p.pid)!=(0x2e8a,0x000a):
    raise SystemExit('Expected Pico SDK USB serial device; no reset attempted')
s=serial.Serial()
s.port=port
s.baudrate=1200
s.dtr=False
try:
    s.open()
    time.sleep(0.2)
except serial.SerialException:
    # Setting 1200 baud can disconnect the SDK USB device before open finishes.
    # Windows can briefly retain its COM entry after the reset has succeeded.
    # The PowerShell stage must still verify a newly appeared RP2040 boot drive.
    deadline=time.monotonic()+2
    while any(p.device==port for p in list_ports.comports()) and time.monotonic()<deadline:
        time.sleep(0.1)
    if any(p.device==port for p in list_ports.comports()):
        raise
finally:
    s.close()
print('Pico USB reset requested; waiting for its BOOTSEL drive.')
'@
& $python -c $resetScript $Port (Join-Path $projectRoot 'tmp/pico-tools-python')
if($LASTEXITCODE) { throw 'Pico USB reset failed' }
$deadline=[DateTime]::UtcNow.AddSeconds(15)
do {
    $volumes=@([System.IO.DriveInfo]::GetDrives() | Where-Object { $_.IsReady -and $_.VolumeLabel -eq 'RPI-RP2' })
    if($volumes.Count) { break }
    Start-Sleep -Milliseconds 300
} while([DateTime]::UtcNow -lt $deadline)
if($volumes.Count -ne 1) { throw 'Expected exactly one newly connected RPI-RP2 drive; no file copied.' }
$info=Join-Path $volumes[0].RootDirectory.FullName 'INFO_UF2.TXT'
if(-not (Test-Path -LiteralPath $info) -or (Get-Content -LiteralPath $info -Raw) -notmatch 'Board-ID: RPI-RP2') {
    throw 'BOOTSEL board identity mismatch; no file copied.'
}
$destination=Join-Path $volumes[0].RootDirectory.FullName (Split-Path $firmware -Leaf)
Copy-Item -LiteralPath $firmware -Destination $destination
Write-Output "Pico $Role firmware copied. It will reboot; verify its role/firmware identity over USB."
