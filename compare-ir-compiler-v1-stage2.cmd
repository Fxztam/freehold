@echo off
setlocal

pushd "%~dp0" || exit /b 1

set "PYTHON=python"
if exist .\.venv\Scripts\python.exe set "PYTHON=.\.venv\Scripts\python.exe"

set "MANIFEST=.\artifacts\fhir-samples\compiler_v1_stage2\manifest.json"
set "TMP_ROOT=%TEMP%\freehold-compare-ir-compiler-v1-stage2-%RANDOM%-%RANDOM%"
set "TMP_PYTHON_ROOT=%TMP_ROOT%\python"
set "TMP_GO_ROOT=%TMP_ROOT%\go"
set "TMP_REPORT_ROOT=%TMP_ROOT%\report"

echo [mode] stage2 check-only; baselines are read-only
echo [mode] temporary output: %TMP_ROOT%

%PYTHON% .\tools\generate_compare_ir_samples.py --manifest "%MANIFEST%" --python-root "%TMP_PYTHON_ROOT%" --go-root "%TMP_GO_ROOT%"
if errorlevel 1 goto :fail

echo.
echo [check] Stage 2 generated Python IR vs generated Go IR
%PYTHON% .\tools\compare_ir_hashes.py --manifest "%MANIFEST%" --python-root "%TMP_PYTHON_ROOT%" --go-root "%TMP_GO_ROOT%" --out "%TMP_REPORT_ROOT%\generated-parity"
if errorlevel 1 goto :fail

if exist "%TMP_ROOT%" rmdir /s /q "%TMP_ROOT%"
popd
exit /b 0

:fail
set "exit_code=%errorlevel%"
if "%exit_code%"=="0" set "exit_code=1"
echo.
echo Compare-IR compiler V1 Stage 2 check failed with exit code %exit_code%.
echo Temporary artifacts kept for inspection: %TMP_ROOT%
popd
exit /b %exit_code%