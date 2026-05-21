@echo off
setlocal enabledelayedexpansion
title ClarityOS v3 - Markoff Engine

echo [v3_markoff] Markoff engine module
echo.

:: --------------------------------------------
:: Paths
:: --------------------------------------------
set "ROOT=%~dp0"
set "LIB=C:\Users\chris\OneDrive\Documents\Library_Clarity_OS\Clarity_Library"
set "HIST=%ROOT%..\..\logs\v3_history.log"

:: --------------------------------------------
:: History: get last command (first token only)
:: --------------------------------------------
if exist "%HIST%" (
    set "last="
    for /f "usebackq tokens=1" %%A in ("%HIST%") do (
        set "last=%%A"
    )
    echo [Markoff] Last command: !last!
) else (
    echo [Markoff] No history file found.
)

echo.

:: ============================================
:: Pattern Extractor Layer (Universal Forms)
:: ============================================
set "FORM="

:: Topology
for %%C in (v3_map v3_layers v3_tree v3_paths v3_modules) do (
    if /I "!last!"=="%%C" set "FORM=TOPOLOGY"
)

:: Dynamics
for %%C in (v3_router v3_trace v3_sync v3_bootstrap) do (
    if /I "!last!"=="%%C" set "FORM=DYNAMICS"
)

:: Progression
for %%C in (v3_step v3_uptime v3_commit) do (
    if /I "!last!"=="%%C" set "FORM=PROGRESSION"
)

:: Cross-Section
for %%C in (v3_diag v3_health v3_scan v3_status v3_markoff v3_history v3_env) do (
    if /I "!last!"=="%%C" set "FORM=CROSS_SECTION"
)

echo [Markoff] Universal form detected: !FORM!
echo.

:: ============================================
:: Map universal form to subsystem
:: ============================================
set "SUBSYS="

if "!FORM!"=="TOPOLOGY"      set "SUBSYS=04_Analytics"
if "!FORM!"=="DYNAMICS"      set "SUBSYS=04_v3_Kernel"
if "!FORM!"=="PROGRESSION"   set "SUBSYS=02_Subsystems"
if "!FORM!"=="CROSS_SECTION" set "SUBSYS=06_Forecasts"

if defined SUBSYS (
    echo [Markoff] Subsystem selected: !SUBSYS!
) else (
    echo [Markoff] No subsystem matched this form.
)

echo.

:: ============================================
:: Scan Clarity Library
:: ============================================
echo [Markoff] Scanning Clarity Library...

if not exist "%LIB%" (
    echo [Markoff] Clarity Library not found at:
    echo   %LIB%
    echo.
    pause
    exit /b 0
)

for /d %%D in ("%LIB%\*") do (
    echo   Found subsystem: %%~nxD
)

echo.

:: ============================================
:: Predictive Runtime (scaffold)
:: ============================================
echo [Markoff] Predicting next moves...

if defined FORM (
    echo   Using universal form: !FORM!
)

if defined SUBSYS (
    echo   Using subsystem: !SUBSYS!
)

echo   (Prediction engine placeholder — ready for weighting, drift, basins)
echo.

:: ============================================
:: Event Stream Logging (Markoff+ Layer 1)
:: ============================================
set "FORECASTS=%LIB%\06_Forecasts"
if not exist "%FORECASTS%" mkdir "%FORECASTS%"

set "EVENT_LOG=%FORECASTS%\event_stream.log"

for /f "tokens=1-3 delims=/- " %%a in ("%date%") do (
    set "YYYY=%%c"
    set "MM=%%a"
    set "DD=%%b"
)
for /f "tokens=1-2 delims=: " %%h in ("%time%") do (
    set "HH=%%h"
    set "MIN=%%i"
)
set "TS=%YYYY%-%MM%-%DD% %HH%:%MIN%"

>>"%EVENT_LOG%" echo %TS% | %last% | %FORM% | %SUBSYS%

echo.
pause
exit /b 0