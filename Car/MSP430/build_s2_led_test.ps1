param([switch]$Switch1, [switch]$Automatic)
$ErrorActionPreference = 'Stop'
$taskCompiler = 'D:/Apps/ccs/tools/compiler/ti-cgt-msp430_21.6.3.LTS'
$taskDevice = 'D:/Apps/ccs/ccs_base/msp430'
$taskProject = Join-Path $PSScriptRoot 's2_led_test'
$taskBuild = Join-Path $taskProject $(if($Automatic) {'build-auto'} elseif($Switch1) {'build-sw1'} else {'Debug'})
$taskDefines = @()
if($Switch1) { $taskDefines += '--define=USE_S1_BUTTON=1' }
if($Automatic) { $taskDefines += '--define=AUTO_LED_TEST=1' }
New-Item -ItemType Directory -Path $taskBuild -Force | Out-Null
Push-Location $taskBuild
try {
    & "$taskCompiler/bin/cl430.exe" '-vmspx' '--data_model=restricted' '--use_hw_mpy=F5' `
        "--include_path=$taskDevice/include" "--include_path=$taskCompiler/include" `
        '--define=__MSP430F5529__' @taskDefines '-g' '--diag_warning=225' `
        '--diag_wrap=off' '--display_error_number' '--silicon_errata=CPU21' `
        '--silicon_errata=CPU22' '--silicon_errata=CPU23' '--silicon_errata=CPU40' `
        (Join-Path $taskProject 'main.c') '-z' '--heap_size=0' '--stack_size=256' `
        '--cinit_hold_wdt=on' "-i$taskDevice/include" "-i$taskDevice/lib/5xx_6xx_FRxx" `
        "-i$taskCompiler/lib" '--reread_libs' '--warn_sections' '--rom_model' `
        '-ms2_led_test.map' '-os2_led_test.out' `
        (Join-Path $PSScriptRoot 'robot_supervisor/lnk_msp430f5529.cmd') '-llibc.a'
    if ($LASTEXITCODE -ne 0) { throw "S2 LED test build failed: $LASTEXITCODE" }
    Write-Host "Built $taskBuild/s2_led_test.out (not uploaded)."
} finally { Pop-Location }
