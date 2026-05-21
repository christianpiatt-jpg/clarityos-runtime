@echo off
echo [v3_step]
echo Command Received: %1
echo Normalized: %~1
echo Interpreter Path: %~dp0
echo Current Directory: %cd%
echo Routing through interpreter...
echo Done.
exit /b 0