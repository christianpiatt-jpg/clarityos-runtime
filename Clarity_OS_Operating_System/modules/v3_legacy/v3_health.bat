@echo off
setlocal enabledelayedexpansion

echo [v3_health]
echo.
echo --- Clarity OS Health Report ---

:: Resolve root
set ROOT=%~dp0..\..\
for %%I in ("%ROOT%") do set ROOT=%%~fI

:: Count modules
set COUNT=0
for %%F in ("%~dp0*.bat") do (
    set /a COUNT+=1
)

:: Count meta layers
set META_COUNT=0
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
    if exist "%ROOT%%%D" (
        set /a META_COUNT+=1
    )
)

:: Surfaces
set SURF_OK=0
if exist "%ROOT%surfaces\" set SURF_OK=1

:: Integrity check (simple)
set INTEGRITY=GOOD
if %COUNT% LSS 10 set INTEGRITY=DEGRADED
if %META_COUNT% LSS 11 set INTEGRITY=DEGRADED
if %SURF_OK%==0 set INTEGRITY=DEGRADED

echo Root:
echo   %ROOT%
echo.

echo Modules:
echo   Total v3 modules: %COUNT%
echo.

echo Meta Layers:
echo   Present: %META_COUNT% of 11
echo.

echo Surfaces:
if %SURF_OK%==1 (
    echo   [OK] surfaces directory
) else (
    echo   [MISSING] surfaces directory
)
echo.

echo Environment:
echo   User: %USERNAME%
echo   Computer: %COMPUTERNAME%
echo   OS: %OS%
echo.

echo System Integrity:
echo   %INTEGRITY%
echo.

echo Health report complete.

endlocal
exit /b 0