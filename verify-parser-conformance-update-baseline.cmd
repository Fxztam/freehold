@echo off
setlocal

pushd "%~dp0" || exit /b 1

echo ===================================================
echo [WARNING] Updating Conformance Baselines
echo This script will update the Go and Python conformance goldens.
echo Make sure these changes are intended and reviewed.
echo ===================================================
echo.

call .\verify-parser-conformance.cmd --update-go-baseline --update-python-baseline %*
if errorlevel 1 goto :fail

popd
exit /b 0

:fail
set "exit_code=%errorlevel%"
if "%exit_code%"=="0" set "exit_code=1"
popd
exit /b %exit_code%
