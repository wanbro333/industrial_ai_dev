@echo off
setlocal
title Industrial AI - Stop

rem The PowerShell script verifies project process identities before stopping them.
"%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe" -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\stop.ps1"
set "cell_stop_exit=%ERRORLEVEL%"

if not "%cell_stop_exit%"=="0" (
    echo.
    echo Shutdown failed. See the error above.
    pause
)

exit /b %cell_stop_exit%
