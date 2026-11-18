param([switch]$EspUart, [switch]$IrDrivingTest, [switch]$Zumo,
      [switch]$PumpDriverVerified, [ValidateRange(1,3)][int]$SpraySeconds=3)
$ErrorActionPreference = 'Stop'
if($Zumo -and $IrDrivingTest) { throw 'Zumo requires ultrasonic stopping; do not combine -Zumo with -IrDrivingTest.' }
if($PumpDriverVerified -and -not $Zumo) { throw 'Pump jobs require the Zumo configuration.' }
$taskCompiler = 'D:/Apps/ccs/tools/compiler/ti-cgt-msp430_21.6.3.LTS'
$taskDevice = 'D:/Apps/ccs/ccs_base/msp430'
$taskProject = Join-Path $PSScriptRoot 'robot_supervisor'
$taskBuildName = if($EspUart) { 'Debug_wifi' } else { 'Debug' }
if($Zumo) { $taskBuildName += '_zumo' }
if($PumpDriverVerified) { $taskBuildName += '_pump' }
if($IrDrivingTest) { $taskBuildName += '_ir_test' }
$taskBuild = Join-Path $taskProject $taskBuildName
$taskDefines = @()
if($EspUart) { $taskDefines += '--define=SUPERVISOR_ESP_UART' }
if($Zumo) { $taskDefines += '--define=ZUMO_BASE=1' }
if($Zumo) { $taskDefines += "--define=PUMP_SPRAY_TICKS=$($SpraySeconds*10)" }
if($PumpDriverVerified) { $taskDefines += '--define=PUMP_DRIVER_VERIFIED=1' }
if($IrDrivingTest) {
    $taskDefines += '--define=IR_DRIVING_TEST=1'
    Write-Host 'IR DRIVING TEST: ultrasonic obstacle stopping is disabled in this separate build.'
}
New-Item -ItemType Directory -Path $taskBuild -Force | Out-Null
Push-Location $taskBuild
try {
    & "$taskCompiler/bin/cl430.exe" '-vmspx' '--data_model=restricted' '--use_hw_mpy=F5' `
        "--include_path=$taskDevice/include" "--include_path=$taskCompiler/include" `
        '--define=__MSP430F5529__' @taskDefines '-g' '--printf_support=minimal' '--diag_warning=225' `
        '--diag_wrap=off' '--display_error_number' '--silicon_errata=CPU21' `
        '--silicon_errata=CPU22' '--silicon_errata=CPU23' '--silicon_errata=CPU40' `
        (Join-Path $taskProject 'main.c') '-z' '--heap_size=0' '--stack_size=512' `
        '--cinit_hold_wdt=on' "-i$taskDevice/include" "-i$taskDevice/lib/5xx_6xx_FRxx" `
        "-i$taskCompiler/lib" '--reread_libs' '--warn_sections' '--rom_model' `
        '-mrobot_supervisor.map' '-orobot_supervisor.out' `
        (Join-Path $taskProject 'lnk_msp430f5529.cmd') '-llibc.a'
    if ($LASTEXITCODE -ne 0) { throw "MSP430 build failed: $LASTEXITCODE" }
    Write-Host "Built $taskBuild/robot_supervisor.out (not uploaded)."
} finally { Pop-Location }
