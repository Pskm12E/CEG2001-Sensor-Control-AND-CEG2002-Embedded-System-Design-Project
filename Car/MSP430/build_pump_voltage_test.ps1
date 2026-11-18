$ErrorActionPreference = 'Stop'
$taskCompiler = 'D:/Apps/ccs/tools/compiler/ti-cgt-msp430_21.6.3.LTS'
$taskDevice = 'D:/Apps/ccs/ccs_base/msp430'
$taskProject = Join-Path $PSScriptRoot 'pump_voltage_test'
$taskBuild = Join-Path $taskProject 'Debug'
New-Item -ItemType Directory -Path $taskBuild -Force | Out-Null
Push-Location $taskBuild
try {
    & "$taskCompiler/bin/cl430.exe" '-vmspx' '--data_model=restricted' '--use_hw_mpy=F5' `
        "--include_path=$taskDevice/include" "--include_path=$taskCompiler/include" `
        '--define=__MSP430F5529__' '-g' '--diag_warning=225' `
        '--diag_wrap=off' '--display_error_number' '--silicon_errata=CPU21' `
        '--silicon_errata=CPU22' '--silicon_errata=CPU23' '--silicon_errata=CPU40' `
        (Join-Path $taskProject 'main.c') '-z' '--heap_size=0' '--stack_size=256' `
        '--cinit_hold_wdt=on' "-i$taskDevice/include" "-i$taskDevice/lib/5xx_6xx_FRxx" `
        "-i$taskCompiler/lib" '--reread_libs' '--warn_sections' '--rom_model' `
        '-mpump_voltage_test.map' '-opump_voltage_test.out' `
        (Join-Path $PSScriptRoot 'robot_supervisor/lnk_msp430f5529.cmd') '-llibc.a'
    if ($LASTEXITCODE -ne 0) { throw "Pump voltage test build failed: $LASTEXITCODE" }
    Write-Host "Built $taskBuild/pump_voltage_test.out (not uploaded)."
} finally { Pop-Location }
