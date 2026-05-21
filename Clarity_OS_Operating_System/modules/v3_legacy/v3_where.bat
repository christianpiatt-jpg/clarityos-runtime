@echo off
setlocal enabledelayedexpansion

echo [v3_where]
echo.
echo Command Queried: %1
echo.

set CMD=%1

:: Kernel commands
for %%K in (
    v3_status
    v3_kernel_info
    v3_kernel_banner
    v3_state
) do (
    if /I "!CMD!"=="%%K" (
        echo Location: Kernel Layer
        echo Module Path: %~dp0%%K.bat
        goto :done
    )
)

:: Core extensions
for %%C in (
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
) do (
    if /I "!CMD!"=="%%C" (
        echo Location: Core Extension Layer
        echo Module Path: %~dp0%%C.bat
        goto :done
    )
)

:: Local commands
if /I "%CMD%"=="quick" (
    echo Location: Local Command
    echo Handler: quick card
    goto :done
)

if /I "%CMD%"=="phone" (
    echo Location: Local Command
    echo Handler: phone card
    goto :done
)

:: Fallback
echo Location: Unknown
echo No module or command found.

:done
echo.
echo Lookup complete.
endlocal
exit /b 0