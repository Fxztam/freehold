@echo off
setlocal

pushd "%~dp0" || exit /b 1

echo [1/17] Regenerate Go AST
cmd /c "cd /d go-frontend && call .\go-parse-tests-language-modules.cmd"
if errorlevel 1 goto :fail

echo.
echo [2/17] Verify Go diagnostics
python ".\tools\verify_go_diagnostics.py"
if errorlevel 1 goto :fail

echo.
echo [3/17] Verify Go semantic diagnostics
call ".\verify-go-semantic-diagnostics.cmd"
if errorlevel 1 goto :fail

echo.
echo [4/17] Verify Go semantic projects
call ".\verify-go-semantic-projects.cmd"
if errorlevel 1 goto :fail

echo.
echo [5/17] Verify spec diagnostics
call ".\verify-spec-diagnostics.cmd"
if errorlevel 1 goto :fail

echo.
echo [6/17] Compare semantic diagnostics
call ".\compare-semantic-diagnostics.cmd"
if errorlevel 1 goto :fail

echo.
echo [7/17] Generate gRPC proto artifacts
call ".\generate-grpc-proto-artifacts.cmd"
if errorlevel 1 goto :fail

echo.
echo [8/17] Generate Go codegen artifacts
call ".\generate-go-codegen-artifacts.cmd"
if errorlevel 1 goto :fail

echo.
echo [9/17] Verify Go feature matrix
call ".\verify-go-feature-matrix.cmd"
if errorlevel 1 goto :fail

echo.
echo [10/17] Generate DHParser parser code
call ".\generate-dhparser-parser.cmd"
if errorlevel 1 goto :fail

echo.
echo [11/17] Regenerate DHParser AST
call ".\dhparser-parse-tests-language-modules.cmd"
if errorlevel 1 goto :fail

echo.
echo [12/17] Compare parser status
call ".\compare-parser-status.cmd"
if errorlevel 1 goto :fail

echo.
echo [13/17] Compare parse errors
call ".\compare-parse-errors.cmd"
if errorlevel 1 goto :fail

echo.
echo [14/17] Compare AST shape
call ".\compare-ast-shape.cmd"
if errorlevel 1 goto :fail

echo.
echo [15/17] Compare semantic AST
call ".\compare-ast-semantic.cmd"
if errorlevel 1 goto :fail

echo.
echo [16/17] Verify additive test line
call ".\verify-additive-test-line.cmd"
if errorlevel 1 goto :fail

echo.
echo [17/17] Go tests
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