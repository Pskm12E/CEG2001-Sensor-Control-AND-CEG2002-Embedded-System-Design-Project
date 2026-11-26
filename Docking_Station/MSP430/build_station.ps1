param([Parameter(Mandatory)][ValidateSet('standalone','coordinated')][string]$Variant)
$ErrorActionPreference = 'Stop'
$compiler = if ($env:MSP430_CGT_ROOT) { $env:MSP430_CGT_ROOT } else { 'D:/Apps/ccs/tools/compiler/ti-cgt-msp430_21.6.3.LTS' }
$device = if ($env:MSP430_DEVICE_ROOT) { $env:MSP430_DEVICE_ROOT } else { 'D:/Apps/ccs/ccs_base/msp430' }
$folder = if ($Variant -eq 'standalone') { 'standalone' } else { 'waterlevel' }
$source = Join-Path $PSScriptRoot $folder
$build = Join-Path $source 'build'
$cl430 = Join-Path $compiler 'bin/cl430.exe'
if (!(Test-Path -LiteralPath $cl430) -or !(Test-Path -LiteralPath (Join-Path $device 'include/msp430f5529.h'))) {
    throw 'Set MSP430_CGT_ROOT and MSP430_DEVICE_ROOT to your installed TI compiler and device-support directories.'
}
New-Item -ItemType Directory -Path $build -Force | Out-Null
Push-Location $build
try {
    $options = @('-vmspx','--data_model=restricted','--use_hw_mpy=F5','--define=__MSP430F5529__',
        "--include_path=$device/include","--include_path=$compiler/include",'--printf_support=minimal',
        '--silicon_errata=CPU21','--silicon_errata=CPU22','--silicon_errata=CPU23','--silicon_errata=CPU40')
    & $cl430 @options (Join-Path $source 'main.c') (Join-Path $source 'lcd16.c') '-z' '--heap_size=0' '--stack_size=512' '--cinit_hold_wdt=on' "-i$device/include" "-i$device/lib/5xx_6xx_FRxx" "-i$compiler/lib" '--reread_libs' '--rom_model' '-mdock.map' '-odock.out' (Join-Path $source 'lnk_msp430f5529.cmd') '-llibc.a'
    if ($LASTEXITCODE -ne 0) { throw "Station build failed for $Variant (exit $LASTEXITCODE)." }
    Write-Host "Built $build/dock.out ($Variant)."
} finally { Pop-Location }
