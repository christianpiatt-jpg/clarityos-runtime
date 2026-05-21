@echo off
setlocal enabledelayedexpansion

echo [v3_log]
echo.

:: Path to log file
set LOGFILE=%~dp0..\..\system.log

:: If no argument, show usage
if "%1"=="" (
    echo Usage:
    echo   v3_log "message"
    echo.
    echo Log file:
    echo   %LOGFILE%
    echo.
    echo No entry written.
    endlocal
    exit /b 0
)

:: Append timestamped entry
echo [%DATE% %TIME%] %*>> "%LOGFILE%"

echo Entry written:
echo   [%DATE% %TIME%] %*
echo.
echo Log file:
echo   %LOGFILE%
echo.
echo Logging complete.

endlocal
exit /b 0