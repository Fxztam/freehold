@echo off
setlocal
pushd "%~dp0" || exit /b 1

set PYTHON=python
if exist ..\.venv\Scripts\python.exe set PYTHON=..\.venv\Scripts\python.exe
if exist .venv\Scripts\python.exe set PYTHON=.\.venv\Scripts\python.exe

set "PYTHONPATH=..;%PYTHONPATH%"

echo [1/2] Verifying Freehold contractual correctness...
"%PYTHON%" -m freehold verify App.fh --prover z3
if errorlevel 1 goto :fail

echo [2/2] Generating and compiling native executable in ./bin...
"%PYTHON%" -m freehold build-exe App.fh --output-dir ./bin --executable-name my_app
if errorlevel 1 goto :fail

echo.
echo [OK] Build completed successfully!
echo Run the binary with: .\bin\my_app.exe
popd
exit /b 0

:fail
echo.
echo [ERROR] Build process failed.
popd
exit /b 1
