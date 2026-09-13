@echo off
setlocal
title Industrial AI - Start

rem Resolve the script relative to this file, including paths containing spaces.
"%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe" -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\start.ps1" %*
set "cell_start_exit=%ERRORLEVEL%"

if not "%cell_start_exit%"=="0" (
    echo.
    echo Startup failed. See the error above.
    pause
)

exit /b %cell_start_exit%
