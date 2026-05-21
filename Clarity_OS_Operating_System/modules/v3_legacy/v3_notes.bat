@echo off
setlocal enabledelayedexpansion

echo [v3_notes]
echo.

:: Path to notes file
set NOTES=%~dp0..\..\notes.txt

if not exist "%NOTES%" (
    echo No notes file found.
    echo Expected at:
    echo   %NOTES%
    echo.
    endlocal
    exit /b 0
)

echo --- Notes File ---
echo Location:
echo   %NOTES%
echo.

type "%NOTES%"

echo.
echo Notes display complete.

endlocal
exit /b 0