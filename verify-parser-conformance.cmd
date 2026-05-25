@echo off
setlocal

pushd "%~dp0" || exit /b 1

echo [1/16] Regenerate Go AST
cmd /c "cd /d go-frontend && call .\go-parse-tests-language-modules.cmd"
if errorlevel 1 goto :fail

echo.
echo [2/16] Verify Go diagnostics
python ".\tools\verify_go_diagnostics.py"
if errorlevel 1 goto :fail

echo.
echo [3/16] Verify Go semantic diagnostics
call ".\verify-go-semantic-diagnostics.cmd"
if errorlevel 1 goto :fail

echo.
echo [4/16] Verify spec diagnostics
call ".\verify-spec-diagnostics.cmd"
if errorlevel 1 goto :fail

echo.
echo [5/16] Compare semantic diagnostics
call ".\compare-semantic-diagnostics.cmd"
if errorlevel 1 goto :fail

echo.
echo [6/16] Generate gRPC proto artifacts
call ".\generate-grpc-proto-artifacts.cmd"
if errorlevel 1 goto :fail

echo.
echo [7/16] Generate Go codegen artifacts
call ".\generate-go-codegen-artifacts.cmd"
if errorlevel 1 goto :fail

echo.
echo [8/16] Verify Go feature matrix
call ".\verify-go-feature-matrix.cmd"
if errorlevel 1 goto :fail

echo.
echo [9/16] Generate DHParser parser code
call ".\generate-dhparser-parser.cmd"
if errorlevel 1 goto :fail

echo.
echo [10/16] Regenerate DHParser AST
call ".\dhparser-parse-tests-language-modules.cmd"
if errorlevel 1 goto :fail

echo.
echo [11/16] Compare parser status
call ".\compare-parser-status.cmd"
if errorlevel 1 goto :fail

echo.
echo [12/16] Compare parse errors
call ".\compare-parse-errors.cmd"
if errorlevel 1 goto :fail

echo.
echo [13/16] Compare AST shape
call ".\compare-ast-shape.cmd"
if errorlevel 1 goto :fail

echo.
echo [14/16] Compare semantic AST
call ".\compare-ast-semantic.cmd"
if errorlevel 1 goto :fail

echo.
echo [15/16] Verify additive test line
call ".\verify-additive-test-line.cmd"
if errorlevel 1 goto :fail

echo.
echo [16/16] Go tests
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