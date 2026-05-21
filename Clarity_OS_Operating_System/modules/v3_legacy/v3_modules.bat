@echo off
echo [v3_modules]
echo.
echo --- Clarity OS Modules (v3) ---
echo Location: %~dp0
echo.
dir /b "%~dp0" | findstr /R "\.bat$"
echo.
echo Module listing complete.
exit /b 0