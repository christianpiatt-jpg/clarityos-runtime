@echo off
setlocal enabledelayedexpansion

echo [v3_tree]
echo.
echo --- Clarity OS Tree ---

:: Resolve root
set ROOT=%~dp0..\..\
for %%I in ("%ROOT%") do set ROOT=%%~fI
echo %ROOT%

:: Modules
echo +-- modules
echo ^|   +-- v3
for %%F in ("%~dp0*.bat") do (
    echo ^|       +-- %%~nxF
)

:: Surfaces
set SURF=%~dp0..\..\surfaces\
for %%I in ("%SURF%") do set SURF=%%~fI
echo +-- surfaces
for %%F in ("%SURF%\*") do (
    echo ^|       +-- %%~nxF
)

:: Meta Layers
echo +-- meta_layers
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
    echo         +-- %%D
)

echo.
echo Tree complete.

endlocal
exit /b 0