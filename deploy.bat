@echo off
REM ============================================================
REM  ClarityOS Cloud  -  single-command Cloud Run deploy
REM
REM  Requires:  gcloud CLI installed and `gcloud auth login` done.
REM  First run: `gcloud config set project YOUR_PROJECT_ID`
REM
REM  Stamps a fresh UTC timestamp into BUILD_VERSION before each
REM  build. That file is COPY'd in the Dockerfile, so the resulting
REM  image always has a unique digest and Cloud Run always sees a
REM  new revision.
REM
REM  Build context is governed by .gcloudignore (upload) and
REM  .dockerignore (image). Both are explicit allow-lists; only the
REM  three runtime modules + requirements.txt + Dockerfile +
REM  BUILD_VERSION end up in the image.
REM ============================================================

setlocal EnableDelayedExpansion
cd /d "%~dp0"

set SERVICE=clarity-engine
set REGION=us-east4

REM Build a yyyymmddHHMMSS UTC stamp via PowerShell (works on every
REM modern Windows without needing wmic, which is being deprecated).
for /f %%I in ('powershell -NoProfile -Command "[DateTime]::UtcNow.ToString('yyyyMMddHHmmss')"') do set BUILD_TAG=%%I

if "%BUILD_TAG%"=="" (
    echo [error] Could not generate build tag. Is PowerShell on PATH?
    exit /b 1
)

REM Stamp the cache-bust marker. Trailing newline is fine; Docker COPY
REM treats this as a small text file and the contents change every run.
> BUILD_VERSION echo %BUILD_TAG%

echo.
echo ================================================================
echo   Deploying %SERVICE% to Cloud Run (%REGION%)
echo   Build tag: %BUILD_TAG%
echo   Source:    %CD%
echo ================================================================
echo.

gcloud run deploy %SERVICE% ^
    --source . ^
    --region %REGION% ^
    --platform managed ^
    --allow-unauthenticated ^
    --port 8080

if errorlevel 1 (
    echo.
    echo [error] Deploy failed. Common causes:
    echo   - gcloud not authenticated:  run "gcloud auth login"
    echo   - no project set:            run "gcloud config set project YOUR_PROJECT_ID"
    echo   - billing disabled on project
    pause
    exit /b 1
)

echo.
echo ================================================================
echo   Deploy complete (build tag %BUILD_TAG%).
echo   Verify:
echo     gcloud run services describe %SERVICE% --region %REGION% ^^
echo       --format="value(status.latestReadyRevisionName,status.url)"
echo ================================================================
pause
