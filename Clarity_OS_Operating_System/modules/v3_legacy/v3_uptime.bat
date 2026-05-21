@echo off
setlocal enabledelayedexpansion

echo [v3_uptime]
echo.

:: Path to uptime file
set UPTIME_FILE=%~dp0..\..\uptime.txt

:: If uptime file does not exist, create it
if not exist "%UPTIME_FILE%" (
    echo Creating uptime record...
    echo Session Start: %DATE% %TIME%> "%UPTIME_FILE%"
)

:: Read uptime file
for /f "tokens=1,* delims=:" %%A in ('findstr /B "Session Start" "%UPTIME_FILE%"') do (
    set START_TIME=%%B
)

echo --- Clarity OS Uptime ---
echo Start Time:%START_TIME%
echo.

echo Current Time:
echo   %DATE% %TIME%
echo.

echo Uptime file:
echo   %UPTIME_FILE%
echo.

echo Uptime report complete.

endlocal
exit /b 0