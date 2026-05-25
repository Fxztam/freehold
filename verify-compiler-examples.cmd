@echo off
setlocal EnableExtensions

pushd "%~dp0" || exit /b 1

set "OUT=.tmp\compiler_examples"
set "FAIL=0"

if exist "%OUT%" rmdir /s /q "%OUT%"
mkdir "%OUT%" >nul 2>nul

call :supported 01_minimal_app examples\compiler_v1\01_minimal_app\App\Main.fh
call :supported 02_records_functions examples\compiler_v1\02_records_functions\App\Main.fh
call :supported 03_cross_module_calls examples\compiler_v1\03_cross_module_calls\App\Main.fh
call :supported 04_result_abort examples\compiler_v1\04_result_abort\App\Main.fh
call :supported 05_runtime_builtins examples\compiler_v1\05_runtime_builtins\App\Main.fh
call :supported 06_integer_big_loop examples\compiler_v1\06_integer_big_loop\App\Main.fh

call :unsupported unsupported_generic_function examples\compiler_v1\unsupported\generic_function\App\Main.fh FH-GOCODEGEN-0001
call :unsupported unsupported_grpc_binding examples\compiler_v1\unsupported\grpc_binding\App\Main.fh FH-GOCODEGEN-0001

call :supported old_BigNumbers examples\BigNumbers.fh
call :supported old_ChudnovskyFeynmanPoint examples\ChudnovskyFeynmanPoint.fh
call :supported old_ChudnovskyPi examples\ChudnovskyPi.fh
call :supported old_epsilon_demo examples\epsilon_demo.fh
call :supported old_GaussLegendrePi examples\GaussLegendrePi.fh
call :supported old_hello_cli examples\hello_cli.fh
call :supported old_JsonStringifySmoke examples\JsonStringifySmoke.fh
call :supported old_RecordTemplateSmoke examples\RecordTemplateSmoke.fh

call :unsupported old_banking_records examples\banking_records.fh FH-GOCODEGEN-0001
call :unsupported old_concurrent_grpc_channel_demo examples\concurrent_grpc_channel_demo.fh FH-GOCODEGEN-0001
call :unsupported old_retail_cli_demo_v11f examples\retail_cli_demo_v11f.fh FH-GOCODEGEN-0001
call :unsupported old_std_io_console_demo examples\std_io_console_demo.fh FH-GOCODEGEN-0001

if not "%FAIL%"=="0" (
    echo.
    echo [FAIL] Compiler example smoke failed.
    popd
    exit /b 1
)

echo.
echo [OK] Compiler example smoke passed.
popd
exit /b 0

:supported
set "NAME=%~1"
set "ENTRY=%~2"
set "PROJECT_OUT=%OUT%\%NAME%"
echo.
echo [EXAMPLE] %NAME%
python -m freehold verify "%ENTRY%"
if errorlevel 1 (
    echo [FAIL] verification failed: %NAME%
    set "FAIL=1"
    exit /b 0
)
python -m freehold go-codegen-project "%ENTRY%" --output-dir "%PROJECT_OUT%" --json "%PROJECT_OUT%\_project.json"
if errorlevel 1 (
    echo [FAIL] Go project codegen failed: %NAME%
    set "FAIL=1"
    exit /b 0
)
pushd "%PROJECT_OUT%"
call build.cmd
set "BUILD_EXIT=%ERRORLEVEL%"
popd
if not "%BUILD_EXIT%"=="0" (
    echo [FAIL] generated Go build failed: %NAME%
    set "FAIL=1"
    exit /b 0
)
echo [OK] %NAME%
exit /b 0

:unsupported
set "NAME=%~1"
set "ENTRY=%~2"
set "EXPECTED=%~3"
set "PROJECT_OUT=%OUT%\%NAME%"
echo.
echo [UNSUPPORTED] %NAME%
python -m freehold verify "%ENTRY%"
if errorlevel 1 (
    echo [FAIL] frontend verification failed before codegen: %NAME%
    set "FAIL=1"
    exit /b 0
)
python -m freehold go-codegen-project "%ENTRY%" --output-dir "%PROJECT_OUT%" --json "%PROJECT_OUT%\_project.json" > "%PROJECT_OUT%.out" 2> "%PROJECT_OUT%.err"
if not errorlevel 1 (
    echo [FAIL] unsupported example unexpectedly generated cleanly: %NAME%
    set "FAIL=1"
    exit /b 0
)
findstr /c:"%EXPECTED%" "%PROJECT_OUT%\_project.json" >nul
if errorlevel 1 (
    echo [FAIL] expected diagnostic %EXPECTED% not found: %NAME%
    set "FAIL=1"
    exit /b 0
)
echo [OK] %NAME% reported %EXPECTED%
exit /b 0