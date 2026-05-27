@echo off
setlocal

pushd "%~dp0" || exit /b 1

set "PYTHON=python"
if exist .\.venv\Scripts\python.exe set "PYTHON=.\.venv\Scripts\python.exe"

set "MANIFEST=.\artifacts\fhir-samples\compiler_v1_stage2\manifest.json"
set "BASELINE_PYTHON_ROOT=.\artifacts\compare-ir\compiler_v1_stage2\python"
set "BASELINE_GO_ROOT=.\artifacts\compare-ir\compiler_v1_stage2\go"
set "REPORT_ROOT=.\artifacts\compare-ir\compiler_v1_stage2\report"

echo [mode] stage2 update-baseline; writing compiler V1 Stage 2 Compare-IR artifacts

%PYTHON% .\tools\generate_compare_ir_samples.py --manifest "%MANIFEST%" --python-root "%BASELINE_PYTHON_ROOT%" --go-root "%BASELINE_GO_ROOT%"
if errorlevel 1 goto :fail

%PYTHON% .\tools\compare_ir_hashes.py --manifest "%MANIFEST%" --python-root "%BASELINE_PYTHON_ROOT%" --go-root "%BASELINE_GO_ROOT%" --out "%REPORT_ROOT%"
if errorlevel 1 goto :fail

%PYTHON% .\tools\verify_stage2_go_project_contracts.py --manifest "%MANIFEST%" --out "%REPORT_ROOT%\go-project-contracts"
if errorlevel 1 goto :fail

popd
exit /b 0

:fail
set "exit_code=%errorlevel%"
if "%exit_code%"=="0" set "exit_code=1"
echo.
echo Compare-IR compiler V1 Stage 2 baseline update failed with exit code %exit_code%.
popd
exit /b %exit_code%