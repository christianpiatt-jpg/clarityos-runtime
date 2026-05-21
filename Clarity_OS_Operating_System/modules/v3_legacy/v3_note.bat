@echo off
setlocal enabledelayedexpansion

echo [v3_note]
echo.

:: Path to notes file
set NOTES=%~dp0..\..\notes.txt

:: If no argument, show usage
if "%1"=="" (
    echo Usage:
    echo   v3_note "your note here"
    echo.
    echo Notes file:
    echo   %NOTES%
    echo.
    echo No note written.
    endlocal
    exit /b 0
)

:: Append timestamped note
echo [%DATE% %TIME%] %*>> "%NOTES%"

echo Note added:
echo   [%DATE% %TIME%] %*
echo.
echo Notes file:
echo   %NOTES%
echo.
echo Note entry complete.

endlocal
exit /b 0