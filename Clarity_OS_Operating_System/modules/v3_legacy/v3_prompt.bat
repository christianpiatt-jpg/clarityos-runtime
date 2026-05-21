@echo off
:: v3_prompt — dynamic operator prompt

setlocal enabledelayedexpansion

:: Build prompt string
set _TIME=%TIME:~0,8%
set _DATE=%DATE%
set _USER=%USERNAME%

echo.
echo ClarityOS v3 [!_USER!] [!_DATE! ! _TIME!]
echo Ready.
echo.

endlocal
exit /b 0