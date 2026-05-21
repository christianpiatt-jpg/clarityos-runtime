@echo off
echo [v3_trace]
echo Command Received: %1
echo Normalized: %~1
echo
echo --- Trace Start ---
echo Checking kernel commands...
echo   - v3_status
echo   - v3_kernel_info
echo   - v3_kernel_banner
echo   - v3_state
echo Checking core extensions...
echo   - v3_step
echo   - v3_diag
echo   - v3_router
echo Checking local commands...
echo   - quick card
echo   - phone card
echo Checking fallback...
echo --- Trace End ---
echo
echo Trace complete.
exit /b 0