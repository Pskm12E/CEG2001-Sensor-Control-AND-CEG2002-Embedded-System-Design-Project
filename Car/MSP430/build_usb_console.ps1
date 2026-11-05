$ErrorActionPreference = 'Stop'
& 'D:\Apps\ccs\tools\node\node.exe' (Join-Path $PSScriptRoot 'tools\ccs-cli.cjs') `
    '-workspace' $PSScriptRoot '-application' 'com.ti.ccs.apps.buildProject' `
    '-ccs.projects' 'robot_usb_console' '-ccs.configuration' 'Debug' `
    '-ccs.buildType' 'incremental' '-ccs.listProblems'
exit $LASTEXITCODE
