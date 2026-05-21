@echo off
echo [v3_clear]

:: No arguments = show usage
if "%~1"=="" (
    echo Usage: v3_clear logs ^| all
    exit /b 0
)

:: Clear only system.log
if /I "%1"=="logs" (
    > "%~dp0..\..\system.log" echo.
    echo Logs cleared.
    exit /b 0
)

:: Clear system.log, uptime.txt, and notes.txt
if /I "%1"=="all" (
    > "%~dp0..\..\system.log" echo.
    > "%~dp0..\..\uptime.txt" echo.
    > "%~dp0..\..\notes.txt" echo.
    echo System state cleared.
    exit /b 0
)

echo Unknown option: %1
exit /b 0