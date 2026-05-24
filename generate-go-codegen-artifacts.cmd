@echo off
setlocal

pushd "%~dp0" || exit /b 1
python ".\tools\generate_go_codegen_artifacts.py"
set "exit_code=%errorlevel%"
popd
exit /b %exit_code%
