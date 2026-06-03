@echo off
setlocal
pushd "%~dp0" || exit /b 1

echo Generate Go semantic artifacts (v2.3)
cmd /c "cd /d go-frontend && go run .\cmd\go-parse-tests-language-modules --semantic --out ..\.tmp\go-semantic-v2_3 ..\tests\language_modules_v2_3"
if errorlevel 1 goto :fail

echo.
python ".\tools\verify_go_semantic_diagnostics_v2_3.py"
if errorlevel 1 goto :fail

popd
exit /b 0

:fail
set "exit_code=%errorlevel%"
if "%exit_code%"=="0" set "exit_code=1"
echo.
echo Verify Go semantic diagnostics (v2.3) failed with exit code %exit_code%.
exit /b %exit_code%
