@echo off
:: v3_bootstrap — full ignition sequence

color 0B
cls

echo ============================================
echo        ClarityOS v3 — Bootstrap Engine
echo ============================================
echo.

echo [1/4] Running repair engine...
call "%~dp0v3_repair.bat"
echo.

echo [2/4] Running sync engine...
call "%~dp0v3_sync.bat"
echo.

echo [3/4] Running boot sequence...
call "%~dp0v3_boot.bat"
echo.

echo [4/4] Entering operator shell...
echo.

call "%~dp0v3_shell.bat"

exit /b 0