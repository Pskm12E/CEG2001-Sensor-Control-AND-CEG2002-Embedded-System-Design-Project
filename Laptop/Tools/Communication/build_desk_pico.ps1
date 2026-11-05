$ErrorActionPreference='Stop'
$projectRoot=[System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot '../../..'))
$python=Join-Path $env:USERPROFILE '.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe'
& $python (Join-Path $PSScriptRoot 'configure.py')
if($LASTEXITCODE) { throw 'Network configuration failed' }
$picoRoot=Join-Path $env:USERPROFILE '.pico-sdk'
$cmake=Join-Path $picoRoot 'cmake/v4.3.4/bin/cmake.exe'
$source=Join-Path $projectRoot 'Laptop/Pico_W/laptop_wifi_bridge'
$build=Join-Path $source 'build'
& $cmake -S $source -B $build -G Ninja "-DPICO_SDK_PATH=$picoRoot/sdk/2.3.1" "-DPICO_TOOLCHAIN_PATH=$picoRoot/toolchain/15_2_Rel1" "-DCMAKE_MAKE_PROGRAM=$picoRoot/ninja/v1.13.2/ninja.exe" "-Dpioasm_DIR=$picoRoot/tools/2.3.1/pioasm" "-Dpicotool_DIR=$picoRoot/picotool/2.3.1/picotool" '-DCMAKE_BUILD_TYPE=Release' '-DPICO_NO_PICOTOOL=0'
if($LASTEXITCODE) { throw 'Desk Pico configuration failed' }
& $cmake --build $build --parallel 4
if($LASTEXITCODE) { throw 'Desk Pico build failed' }
