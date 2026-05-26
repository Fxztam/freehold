@echo off
setlocal
pushd "%~dp0" || exit /b 1

python ".\tools\verify_go_semantic_projects.py"
if errorlevel 1 goto :fail

popd
exit /b 0

:fail
set "exit_code=%errorlevel%"
if "%exit_code%"=="0" set "exit_code=1"
echo.
echo Verify Go semantic projects failed with exit code %exit_code%.
exit /b %exit_code%
