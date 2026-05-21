@echo off
setlocal enabledelayedexpansion

echo [v3_scan]
echo.
echo --- Clarity OS Structural Scan ---

:: Root resolution
set ROOT=%~dp0..\..\
for %%I in ("%ROOT%") do set ROOT=%%~fI

echo Root:
echo   %ROOT%
echo.

:: ------------------------------
:: 1. Check required v3 modules
:: ------------------------------
echo Modules (v3):
set MISSING=0

for %%M in (
    v3_status
    v3_kernel_info
    v3_kernel_banner
    v3_state
    v3_step
    v3_diag
    v3_router
    v3_trace
    v3_map
    v3_help
    v3_about
    v3_version
    v3_history
    v3_modules
    v3_paths
    v3_env
    v3_where
    v3_tree
    v3_scan
) do (
    if exist "%~dp0%%M.bat" (
        echo   [OK] %%M
    ) else (
        echo   [MISSING] %%M
        set /a MISSING+=1
    )
)

echo.

:: ------------------------------
:: 2. Check surfaces
:: ------------------------------
echo Surfaces:
set SURF=%ROOT%surfaces\
if exist "%SURF%" (
    echo   [OK] surfaces directory
) else (
    echo   [MISSING] surfaces directory
    set /a MISSING+=1
)

if exist "%SURF%PHONE_CARD.txt" (
    echo   [OK] PHONE_CARD.txt
) else (
    echo   [MISSING] PHONE_CARD.txt
    set /a MISSING+=1
)

echo.

:: ------------------------------
:: 3. Check meta layers
:: ------------------------------
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
    if exist "%ROOT%%%D" (
        echo   [OK] %%D
    ) else (
        echo   [MISSING] %%D
        set /a MISSING+=1
    )
)

echo.

:: ------------------------------
:: 4. Summary
:: ------------------------------
echo Summary:
if %MISSING%==0 (
    echo   All required components present.
    echo   System Integrity: GOOD
) else (
    echo   Missing components: %MISSING%
    echo   System Integrity: DEGRADED
)

echo.
echo Scan complete.

endlocal
exit /b 0