@echo off
:: v3_dashboard — operator cockpit

cls
color 0B

echo ============================================
echo           ClarityOS v3 Dashboard
echo ============================================
echo.

echo [System Status]
call "%~dp0v3_status.bat"
echo.

echo [Uptime]
call "%~dp0v3_uptime.bat"
echo.

echo [Health]
call "%~dp0v3_health.bat"
echo.

echo [Environment]
call "%~dp0v3_env.bat"
echo.

echo [Layers]
call "%~dp0v3_layers.bat"
echo.

echo [Modules]
call "%~dp0v3_modules.bat"
echo.

echo [Recent Notes]
type "%~dp0..\..\notes.txt" | more
echo.

echo ============================================
echo Dashboard complete.
echo ============================================

exit /b 0