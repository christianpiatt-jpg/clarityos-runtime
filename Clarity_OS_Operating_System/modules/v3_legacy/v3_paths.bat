@echo off
setlocal enabledelayedexpansion

echo [v3_paths]
echo.

:: Resolve absolute paths
set ROOT_PATH=%~dp0..\..\
for %%I in ("%ROOT_PATH%") do set ROOT_PATH=%%~fI

set MODULES_PATH=%~dp0
for %%I in ("%MODULES_PATH%") do set MODULES_PATH=%%~fI

set SURFACES_PATH=%~dp0..\..\surfaces\
for %%I in ("%SURFACES_PATH%") do set SURFACES_PATH=%%~fI

echo --- Clarity OS Paths ---
echo Root Directory:
echo   %ROOT_PATH%
echo.
echo Modules Directory:
echo   %MODULES_PATH%
echo.
echo Surfaces Directory:
echo   %SURFACES_PATH%
echo.
echo Meta Layers:

for %%D in (
    00_Meta
    01_Environmental_Geometry
    02_Modules
    03_Martial_OS
    04_Executive_Layer
    05_Meta_Executive
    06_Propagation_OS
    07_Global_OS
    08_VA_Simulation
    09_Buddy_Suite
    10_Autoadjust_Engine
) do (
    set TEMP_PATH=%~dp0..\..\%%D\
    for %%I in ("!TEMP_PATH!") do echo   %%~fI
)

echo.
echo Temp Directory:
echo   %TEMP%
echo.
echo Paths complete.

endlocal
exit /b 0