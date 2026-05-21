@echo off
:: v3_commit — snapshot OS state

set ROOT=%~dp0..\..
set COMMITS=%ROOT%\commits

if not exist "%COMMITS%" mkdir "%COMMITS%"

set TS=%DATE:~10,4%-%DATE:~4,2%-%DATE:~7,2%_%TIME:~0,2%-%TIME:~3,2%-%TIME:~6,2%
set TS=%TS: =0%

set FILE=%COMMITS%\commit_%TS%.txt

echo Creating commit: %FILE%
echo --------------------------------------------- > "%FILE%"
echo ClarityOS v3 Commit Snapshot >> "%FILE%"
echo Timestamp: %DATE% %TIME% >> "%FILE%"
echo Operator: %USERNAME% >> "%FILE%"
echo Host: %COMPUTERNAME% >> "%FILE%"
echo --------------------------------------------- >> "%FILE%"
echo. >> "%FILE%"

echo [System Status] >> "%FILE%"
call "%~dp0v3_status.bat" >> "%FILE%"
echo. >> "%FILE%"

echo [Uptime] >> "%FILE%"
call "%~dp0v3_uptime.bat" >> "%FILE%"
echo. >> "%FILE%"

echo [Environment] >> "%FILE%"
call "%~dp0v3_env.bat" >> "%FILE%"
echo. >> "%FILE%"

echo [Modules] >> "%FILE%"
call "%~dp0v3_modules.bat" >> "%FILE%"
echo. >> "%FILE%"

echo [Layers] >> "%FILE%"
call "%~dp0v3_layers.bat" >> "%FILE%"
echo. >> "%FILE%"

echo [Recent Notes] >> "%FILE%"
type "%ROOT%\notes.txt" >> "%FILE%"
echo. >> "%FILE%"

echo Commit complete.
exit /b 0