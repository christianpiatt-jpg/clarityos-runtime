@echo off
:: v3_repair — automatic structural repair engine

echo [v3_repair]
set ROOT=%~dp0..\..
set MODULES=%ROOT%\modules\v3
set META=%ROOT%\..\Clarity_OS_Operating_System

echo Running structural integrity scan...
echo.

:: Check modules directory
if not exist "%MODULES%" (
    echo [ERROR] Modules directory missing. Recreating...
    mkdir "%MODULES%"
) else (
    echo [OK] Modules directory present.
)

:: Check required modules
for %%M in (
    v3_status.bat
    v3_state.bat
    v3_kernel_info.bat
    v3_kernel_banner.bat
    v3_paths.bat
    v3_env.bat
    v3_where.bat
    v3_tree.bat
    v3_scan.bat
    v3_health.bat
    v3_diag.bat
    v3_router.bat
    v3_trace.bat
    v3_map.bat
    v3_help.bat
    v3_about.bat
    v3_version.bat
    v3_history.bat
    v3_modules.bat
    v3_note.bat
    v3_notes.bat
    v3_log.bat
    v3_clear.bat
    v3_uptime.bat
    v3_step.bat
    v3_layers.bat
    v3_prompt.bat
    v3_shell.bat
    v3_skin.bat
    v3_dashboard.bat
    v3_commit.bat
) do (
    if not exist "%MODULES%\%%M" (
        echo [MISSING] %%M — placeholder created.
        echo @echo off> "%MODULES%\%%M"
        echo echo Placeholder for %%M>> "%MODULES%\%%M"
    ) else (
        echo [OK] %%M
    )
)

echo.
echo Structural repair complete.
exit /b 0