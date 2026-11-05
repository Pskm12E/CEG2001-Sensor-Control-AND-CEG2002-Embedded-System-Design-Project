@echo off
set "ROBOT_CONSOLE_PY=%USERPROFILE%\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
if exist "%ROBOT_CONSOLE_PY%" (
  "%ROBOT_CONSOLE_PY%" "%~dp0desk_console.py"
) else (
  py -3 "%~dp0desk_console.py"
)
pause
