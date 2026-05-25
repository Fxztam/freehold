@echo off
setlocal
pushd "%~dp0" || exit /b 1

echo Generate Go semantic artifacts
cmd /c "cd /d go-frontend && go run .\cmd\go-parse-tests-language-modules --semantic --out ..\.tmp\go-semantic ..\tests\language_modules"
if errorlevel 1 goto :fail

echo.
python ".\tools\verify_go_semantic_diagnostics.py" --go ".tmp\go-semantic"
if errorlevel 1 goto :fail

popd
exit /b 0

:fail
set "exit_code=%errorlevel%"
if "%exit_code%"=="0" set "exit_code=1"
echo.
echo Verify Go semantic diagnostics failed with exit code %exit_code%.
exit /b %exit_code%
