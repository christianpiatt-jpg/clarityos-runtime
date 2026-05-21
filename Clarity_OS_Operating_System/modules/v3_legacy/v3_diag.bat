@echo off
echo [v3_diag]
echo --- Environment ---
echo Username: %USERNAME%
echo Computer: %COMPUTERNAME%
echo OS: %OS%
echo Processor: %PROCESSOR_IDENTIFIER%
echo
echo --- Paths ---
echo Interpreter Path: %~dp0
echo Current Directory: %cd%
echo System Root: %SystemRoot%
echo Temp Directory: %TEMP%
echo
echo --- Variables ---
echo Argument 1: %1
echo Argument 2: %2
echo
echo Diagnostics complete.
exit /b 0