@echo off
echo [v3_env]
echo.
echo --- Environment Snapshot ---

echo User:
echo   Username: %USERNAME%
echo   Home: %USERPROFILE%
echo.

echo System:
echo   Computer: %COMPUTERNAME%
echo   OS: %OS%
echo   Processor: %PROCESSOR_IDENTIFIER%
echo.

echo Shell:
echo   Working Directory: %CD%
echo   Interpreter Path: %~dp0
echo.

echo Paths:
echo   Temp: %TEMP%
echo   SystemRoot: %SystemRoot%
echo.

echo Environment snapshot complete.
exit /b 0