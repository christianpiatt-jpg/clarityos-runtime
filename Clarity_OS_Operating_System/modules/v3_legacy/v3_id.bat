@echo off
echo [v3_id]

echo Kernel: v3
echo System: Clarity OS
echo Mode: Operator
echo Root: %~dp0..\..
echo Host: %COMPUTERNAME%
echo User: %USERNAME%
echo Shell: %COMSPEC%
echo Time: %TIME%
echo Date: %DATE%

exit /b 0