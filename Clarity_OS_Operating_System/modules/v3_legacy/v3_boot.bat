@echo off
echo [v3_boot]

call "%~dp0v3_kernel_banner.bat"
echo.
call "%~dp0v3_status.bat"
call "%~dp0v3_health.bat"
call "%~dp0v3_uptime.bat"
echo.
echo Boot sequence complete.
exit /b 0