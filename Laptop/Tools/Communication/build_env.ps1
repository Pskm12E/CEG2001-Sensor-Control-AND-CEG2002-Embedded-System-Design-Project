# Shared Windows tool lookup for the robot firmware builds. Dot-source this file.
function Get-RobotPython {
    if ($env:ROBOT_PYTHON) { return $env:ROBOT_PYTHON }
    return (Get-Command python -CommandType Application -ErrorAction Stop | Select-Object -First 1).Source
}
function Get-RobotArduinoCli {
    if ($env:ARDUINO_CLI) { return $env:ARDUINO_CLI }
    $onPath = Get-Command arduino-cli -CommandType Application -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($onPath) { return $onPath.Source }
    $bundled = Join-Path $env:LOCALAPPDATA 'Programs/Arduino IDE/resources/app/lib/backend/resources/arduino-cli.exe'
    if (Test-Path -LiteralPath $bundled) { return $bundled }
    throw 'Install Arduino CLI or set ARDUINO_CLI to the executable.'
}
function Get-RobotArduinoConfig {
    $config = Join-Path $env:USERPROFILE '.arduinoIDE/arduino-cli.yaml'
    if (Test-Path -LiteralPath $config) { '--config-file'; $config }
}
