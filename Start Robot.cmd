@echo off
setlocal
cd /d "%~dp0Laptop\Dashboard"
if exist ".venv\Scripts\python.exe" goto venv
if exist "%USERPROFILE%\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" goto bundled
where py >nul 2>nul
if not errorlevel 1 goto pylauncher
where python >nul 2>nul
if not errorlevel 1 goto python
echo Python is missing. Install Python 3 and follow Laptop\Dashboard\README.md.
pause
exit /b 1

:venv
".venv\Scripts\python.exe" launch.py %*
goto finished
:bundled
"%USERPROFILE%\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" launch.py %*
goto finished
:pylauncher
py -3 launch.py %*
goto finished
:python
python launch.py %*
:finished
set "robot_launch_status=%errorlevel%"
if not "%robot_launch_status%"=="0" pause
exit /b %robot_launch_status%
