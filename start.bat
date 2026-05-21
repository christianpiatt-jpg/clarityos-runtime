@echo off
REM ============================================================
REM  ClarityOS Cloud  -  single-command local launcher
REM
REM  Just double-click this file (or run `start.bat` from cmd).
REM  It will:
REM    1. Create C:\ClarityOS_Code\.venv if missing
REM    2. Install fastapi + uvicorn + pydantic
REM    3. Start the API on http://localhost:8080
REM
REM  Endpoints:  /markov  /galileo  /library  /tizzy  /health
REM ============================================================

setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo [setup] Creating virtual environment in .venv ...
    python -m venv .venv
    if errorlevel 1 (
        echo [error] Could not create venv. Is Python on your PATH?
        pause
        exit /b 1
    )
)

call ".venv\Scripts\activate.bat"

echo [setup] Installing dependencies ...
python -m pip install --quiet --upgrade pip
python -m pip install --quiet -r requirements.txt
if errorlevel 1 (
    echo [error] Dependency install failed.
    pause
    exit /b 1
)

echo.
echo ================================================================
echo   ClarityOS Cloud running at  http://localhost:8080
echo   POST  /markov   /galileo   /library   /tizzy
echo   GET   /health   /
echo   Press CTRL+C to stop.
echo ================================================================
echo.

uvicorn app:app --host 0.0.0.0 --port 8080 --reload
