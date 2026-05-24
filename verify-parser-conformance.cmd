@echo off
setlocal

pushd "%~dp0" || exit /b 1

echo [1/11] Regenerate Go AST
cmd /c "cd /d go-frontend && call .\go-parse-tests-language-modules.cmd"
if errorlevel 1 goto :fail

echo.
echo [2/11] Verify Go diagnostics
python ".\tools\verify_go_diagnostics.py"
if errorlevel 1 goto :fail

echo.
echo [3/11] Verify spec diagnostics
call ".\verify-spec-diagnostics.cmd"
if errorlevel 1 goto :fail

echo.
echo [4/11] Compare semantic diagnostics
call ".\compare-semantic-diagnostics.cmd"
if errorlevel 1 goto :fail

echo.
echo [5/11] Generate gRPC proto artifacts
call ".\generate-grpc-proto-artifacts.cmd"
if errorlevel 1 goto :fail

echo.
echo [6/11] Regenerate DHParser AST
call ".\dhparser-parse-tests-language-modules.cmd"
if errorlevel 1 goto :fail

echo.
echo [7/11] Compare parser status
call ".\compare-parser-status.cmd"
if errorlevel 1 goto :fail

echo.
echo [8/11] Compare parse errors
call ".\compare-parse-errors.cmd"
if errorlevel 1 goto :fail

echo.
echo [9/11] Compare AST shape
call ".\compare-ast-shape.cmd"
if errorlevel 1 goto :fail

echo.
echo [10/11] Compare semantic AST
call ".\compare-ast-semantic.cmd"
if errorlevel 1 goto :fail

echo.
echo [11/11] Go tests
cmd /c "cd /d go-frontend && go test ./..."
if errorlevel 1 goto :fail

echo.
echo Parser conformance verify passed.
popd
exit /b 0

:fail
set "exit_code=%errorlevel%"
if "%exit_code%"=="0" set "exit_code=1"
echo.
echo Parser conformance verify failed with exit code %exit_code%.
exit /b %exit_code%