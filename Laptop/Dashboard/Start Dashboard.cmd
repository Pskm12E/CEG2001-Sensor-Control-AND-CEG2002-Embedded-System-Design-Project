@echo off
setlocal
call "%~dp0..\..\Start Robot.cmd" %*
exit /b %errorlevel%
