@echo off
setlocal

pushd "%~dp0" || exit /b 1

set "UPDATE_GO_BASELINE=0"
set "UPDATE_PYTHON_BASELINE=0"
set "ENABLE_FHIR_V1_GATE=1"

:parse_args
if "%~1"=="" goto :args_done
if /i "%~1"=="--update-go-baseline" (
	set "UPDATE_GO_BASELINE=1"
	shift
	goto :parse_args
)
if /i "%~1"=="--update-python-baseline" (
	set "UPDATE_PYTHON_BASELINE=1"
	shift
	goto :parse_args
)
if /i "%~1"=="--enable-fhir-v1-gate" (
	set "ENABLE_FHIR_V1_GATE=1"
	shift
	goto :parse_args
)
if /i "%~1"=="--disable-fhir-v1-gate" (
	set "ENABLE_FHIR_V1_GATE=0"
	shift
	goto :parse_args
)
echo Unknown argument: %~1
echo Supported flags: --update-go-baseline --update-python-baseline --enable-fhir-v1-gate --disable-fhir-v1-gate
popd
exit /b 1

:args_done

set "GO_AST_ROOT=.\artifacts\go-ast"
if "%UPDATE_GO_BASELINE%"=="1" goto :go_mode_ready
set "GO_AST_ROOT=%TEMP%\freehold-go-ast-%RANDOM%-%RANDOM%"

:go_mode_ready

set "DHPARSER_PARSER_ROOT=.\artifacts\dhparser-parser"
set "DHPARSER_AST_ROOT=.\artifacts\dhparser-ast"
set "COMPARE_SEMANTIC_DIAGNOSTICS_ROOT=.\artifacts\compare-semantic-diagnostics"
set "COMPARE_PARSE_STATUS_ROOT=.\artifacts\compare-parse-status"
set "COMPARE_PARSE_ERRORS_ROOT=.\artifacts\compare-parse-errors"
set "COMPARE_AST_SHAPE_ROOT=.\artifacts\compare-ast-shape"
set "COMPARE_AST_SEMANTIC_ROOT=.\artifacts\compare-ast-semantic"
set "COMPARE_FHIR_ROOT=.\artifacts\compare-fhir"
set "COMPARE_FHIR_V1_ROOT=.\artifacts\compare-fhir-v1"
set "COMPARE_FHIR_DETERMINISM_ROOT=.\artifacts\compare-fhir-determinism"
set "COMPARE_FHIR_LANGUAGE_MODULES_ROOT=.\artifacts\compare-fhir-language-modules"
if "%UPDATE_PYTHON_BASELINE%"=="1" goto :mode_ready

set "PY_OUT_ROOT=%TEMP%\freehold-py-out-%RANDOM%-%RANDOM%"
set "DHPARSER_PARSER_ROOT=%PY_OUT_ROOT%\dhparser-parser"
set "DHPARSER_AST_ROOT=%PY_OUT_ROOT%\dhparser-ast"
set "COMPARE_SEMANTIC_DIAGNOSTICS_ROOT=%PY_OUT_ROOT%\compare-semantic-diagnostics"
set "COMPARE_PARSE_STATUS_ROOT=%PY_OUT_ROOT%\compare-parse-status"
set "COMPARE_PARSE_ERRORS_ROOT=%PY_OUT_ROOT%\compare-parse-errors"
set "COMPARE_AST_SHAPE_ROOT=%PY_OUT_ROOT%\compare-ast-shape"
set "COMPARE_AST_SEMANTIC_ROOT=%PY_OUT_ROOT%\compare-ast-semantic"
set "COMPARE_FHIR_ROOT=%PY_OUT_ROOT%\compare-fhir"
set "COMPARE_FHIR_V1_ROOT=%PY_OUT_ROOT%\compare-fhir-v1"
set "COMPARE_FHIR_DETERMINISM_ROOT=%PY_OUT_ROOT%\compare-fhir-determinism"
set "COMPARE_FHIR_LANGUAGE_MODULES_ROOT=%PY_OUT_ROOT%\compare-fhir-language-modules"

:mode_ready

if "%UPDATE_GO_BASELINE%"=="1" (
	set "GO_MODE=update-go-baseline"
) else (
	set "GO_MODE=check"
)
if "%UPDATE_PYTHON_BASELINE%"=="1" (
	set "PY_MODE=update-python-baseline"
) else (
	set "PY_MODE=check"
)

echo [mode] go=%GO_MODE% ; python=%PY_MODE%
if "%ENABLE_FHIR_V1_GATE%"=="1" (
	echo [mode] FH-IR V1 gate enabled (default)
) else (
	echo [mode] FH-IR V1 gate disabled via escape flag
)
if "%UPDATE_GO_BASELINE%"=="0" echo [mode] temporary Go AST output: %GO_AST_ROOT%
if "%UPDATE_PYTHON_BASELINE%"=="0" echo [mode] temporary Python outputs root: %PY_OUT_ROOT%

echo [1/22] Regenerate Go AST
cmd /c "cd /d go-frontend && go run .\cmd\go-parse-tests-language-modules --out %GO_AST_ROOT% ..\tests\language_modules"
if errorlevel 1 goto :fail

echo.
echo [2/22] Verify Go diagnostics
python ".\tools\verify_go_diagnostics.py" --go "%GO_AST_ROOT%"
if errorlevel 1 goto :fail

echo.
echo [3/22] Verify grammar consistency
call ".\verify-grammar-consistency.cmd"
if errorlevel 1 goto :fail

echo.
echo [4/22] Verify Go semantic diagnostics
call ".\verify-go-semantic-diagnostics.cmd"
if errorlevel 1 goto :fail

echo.
echo [5/22] Verify Go semantic projects
call ".\verify-go-semantic-projects.cmd"
if errorlevel 1 goto :fail

echo.
echo [6/22] Verify Go project semantic diagnostics
call ".\verify-go-project-semantic-diagnostics.cmd"
if errorlevel 1 goto :fail

echo.
echo [7/22] Verify spec diagnostics
call ".\verify-spec-diagnostics.cmd"
if errorlevel 1 goto :fail

echo.
echo [8/22] Compare semantic diagnostics
python ".\tools\compare_semantic_diagnostics.py" --expected .\tests\language_modules\expected_semantic_diagnostics.json --root .\tests\language_modules --out "%COMPARE_SEMANTIC_DIAGNOSTICS_ROOT%"
if errorlevel 1 goto :fail

echo.
echo [9/22] Generate gRPC proto artifacts
call ".\generate-grpc-proto-artifacts.cmd"
if errorlevel 1 goto :fail

echo.
echo [10/22] Generate Go codegen artifacts
call ".\generate-go-codegen-artifacts.cmd"
if errorlevel 1 goto :fail

echo.
echo [11/22] Verify Go feature matrix
call ".\verify-go-feature-matrix.cmd"
if errorlevel 1 goto :fail

echo.
echo [12/22] Generate DHParser parser code
python ".\tools\generate_dhparser_parser.py" --out "%DHPARSER_PARSER_ROOT%"
if errorlevel 1 goto :fail

echo.
echo [13/22] Regenerate DHParser AST
python ".\tools\dhparser_ast_runner.py" --out "%DHPARSER_AST_ROOT%" .\tests\language_modules
if errorlevel 1 goto :fail

echo.
echo [14/22] Compare parser status
python ".\tools\compare_parser_status.py" --go "%GO_AST_ROOT%" --dhparser "%DHPARSER_AST_ROOT%" --out "%COMPARE_PARSE_STATUS_ROOT%"
if errorlevel 1 goto :fail

echo.
echo [15/22] Compare parse errors
python ".\tools\compare_parse_errors.py" --go "%GO_AST_ROOT%" --dhparser "%DHPARSER_AST_ROOT%" --out "%COMPARE_PARSE_ERRORS_ROOT%"
if errorlevel 1 goto :fail

echo.
echo [16/22] Compare AST shape
python ".\tools\compare_ast_shape.py" --go "%GO_AST_ROOT%" --dhparser "%DHPARSER_AST_ROOT%" --out "%COMPARE_AST_SHAPE_ROOT%"
if errorlevel 1 goto :fail

echo.
echo [17/22] Compare semantic AST
python ".\tools\compare_ast_semantic.py" --go "%GO_AST_ROOT%" --dhparser "%DHPARSER_AST_ROOT%" --out "%COMPARE_AST_SEMANTIC_ROOT%"
if errorlevel 1 goto :fail

echo.
echo [18/22] Compare FH-IR
if "%UPDATE_PYTHON_BASELINE%"=="1" (
	python ".\tools\compare_fhir.py" --out "%COMPARE_FHIR_ROOT%" --update
) else (
	python ".\tools\compare_fhir.py" --out "%COMPARE_FHIR_ROOT%"
)
if errorlevel 1 goto :fail

echo.
echo [19/22] Compare FH-IR determinism
python ".\tools\compare_fhir_determinism.py" --out "%COMPARE_FHIR_DETERMINISM_ROOT%"
if errorlevel 1 goto :fail

echo.
echo [20/22] Compare FH-IR language modules
python ".\tools\compare_fhir_language_modules.py" --profile stable --out "%COMPARE_FHIR_LANGUAGE_MODULES_ROOT%"
if errorlevel 1 goto :fail

if "%ENABLE_FHIR_V1_GATE%"=="1" (
	echo.
	echo [20b/22] Compare FH-IR V1
	if "%UPDATE_PYTHON_BASELINE%"=="1" (
		python ".\tools\compare_fhir.py" --mode project-v1 --expected .\artifacts\fhir-v1 --out "%COMPARE_FHIR_V1_ROOT%" --update
	) else (
		python ".\tools\compare_fhir.py" --mode project-v1 --expected .\artifacts\fhir-v1 --out "%COMPARE_FHIR_V1_ROOT%"
	)
	if errorlevel 1 goto :fail
)

echo.
echo [21/22] Verify additive test line
call ".\verify-additive-test-line.cmd"
if errorlevel 1 goto :fail

echo.
echo [22/22] Go tests
cmd /c "cd /d go-frontend && go test ./..."
if errorlevel 1 goto :fail

echo.
echo Parser conformance verify passed.
if "%UPDATE_GO_BASELINE%"=="0" (
	if exist "%GO_AST_ROOT%" rmdir /s /q "%GO_AST_ROOT%"
)
if "%UPDATE_PYTHON_BASELINE%"=="0" (
	if exist "%PY_OUT_ROOT%" rmdir /s /q "%PY_OUT_ROOT%"
)
popd
exit /b 0

:fail
set "exit_code=%errorlevel%"
if "%exit_code%"=="0" set "exit_code=1"
if "%UPDATE_GO_BASELINE%"=="0" (
	if exist "%GO_AST_ROOT%" rmdir /s /q "%GO_AST_ROOT%"
)
if "%UPDATE_PYTHON_BASELINE%"=="0" (
	if exist "%PY_OUT_ROOT%" rmdir /s /q "%PY_OUT_ROOT%"
)
echo.
echo Parser conformance verify failed with exit code %exit_code%.
exit /b %exit_code%