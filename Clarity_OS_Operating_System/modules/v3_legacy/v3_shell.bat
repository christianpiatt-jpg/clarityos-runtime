@echo off
:: v3_shell — interactive operator shell

setlocal enabledelayedexpansion

:loop
cls
color 0B
echo ClarityOS v3 Shell
echo -------------------
echo Type 'exit' to return to system console.
echo.

set /p _cmd="ClarityOS v3 > "

if /I "!_cmd!"=="exit" (
    echo Exiting ClarityOS v3 shell...
    endlocal
    exit /b 0
)

call "%~dp0..\..\interpreter.bat" !_cmd!
echo.
pause
goto loop