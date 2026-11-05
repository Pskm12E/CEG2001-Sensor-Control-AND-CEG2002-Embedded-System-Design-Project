$ErrorActionPreference = 'Stop'
$mspNode = 'D:\Apps\ccs\tools\node\node.exe'
$mspLauncher = Join-Path $PSScriptRoot 'tools\ccs-cli.cjs'
& $mspNode $mspLauncher '-workspace' $PSScriptRoot `
    '-application' 'com.ti.ccs.apps.buildProject' `
    '-ccs.projects' 'robot_led_test' '-ccs.configuration' 'Debug' `
    '-ccs.buildType' 'incremental' '-ccs.listProblems'
exit $LASTEXITCODE
