@echo off
setlocal

pushd "%~dp0" || exit /b 1

set "PYTHON=python"
if exist .\.venv\Scripts\python.exe set "PYTHON=.\.venv\Scripts\python.exe"

%PYTHON% .\tools\verify_stage3_compiler_core_contracts.py --manifest .\artifacts\stage3\compiler_core_loader_v1\manifest.json --out .\artifacts\stage3\compiler_core_loader_v1\report --build-root .\.tmp\stage3-compiler-core-loader-v1
if errorlevel 1 goto :fail

popd
exit /b 0

:fail
set "exit_code=%errorlevel%"
if "%exit_code%"=="0" set "exit_code=1"
echo.
echo Stage-3 compiler_core_loader_v1 verify failed with exit code %exit_code%.
popd
exit /b %exit_code%
