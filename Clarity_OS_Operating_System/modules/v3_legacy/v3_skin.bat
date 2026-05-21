@echo off
:: v3_skin — visual theme engine

if "%~1"=="" (
    echo [v3_skin]
    echo Usage: v3_skin default ^| cyan ^| dark
    exit /b 0
)

:: Default theme (classic)
if /I "%1"=="default" (
    color 07
    echo Theme set: default
    exit /b 0
)

:: Cyan on black (ClarityOS operator theme)
if /I "%1"=="cyan" (
    color 0B
    echo Theme set: cyan/black
    exit /b 0
)

:: Dark mode (dim cyan on black)
if /I "%1"=="dark" (
    color 01
    echo Theme set: dark mode
    exit /b 0
)

echo Unknown theme: %1
exit /b 0