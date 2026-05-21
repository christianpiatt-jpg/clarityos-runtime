@echo off
:: v3_sync — synchronize OS components

echo [v3_sync]
set ROOT=%~dp0..\..
set MODULES=%ROOT%\modules\v3
set SURFACES=%ROOT%\surfaces
set COMMITS=%ROOT%\commits
set NOTES=%ROOT%\notes.txt

echo Running synchronization cycle...
echo.

:: Ensure surfaces directory exists
if not exist "%SURFACES%" (
    echo [MISSING] surfaces directory — creating...
    mkdir "%SURFACES%"
) else (
    echo [OK] surfaces directory
)

:: Ensure commits directory exists
if not exist "%COMMITS%" (
    echo [MISSING] commits directory — creating...
    mkdir "%COMMITS%"
) else (
    echo [OK] commits directory
)

:: Ensure notes file exists
if not exist "%NOTES%" (
    echo [MISSING] notes.txt — creating...
    echo ClarityOS Notes File > "%NOTES%"
) else (
    echo [OK] notes.txt
)

:: Count modules
set COUNT=0
for %%F in ("%MODULES%\*.bat") do (
    set /a COUNT+=1
)

echo [Modules] %COUNT% modules synchronized.

:: Timestamp sync
set TS=%DATE% %TIME%
echo Last Sync: %TS% > "%ROOT%\last_sync.txt"

echo.
echo Synchronization complete.
exit /b 0