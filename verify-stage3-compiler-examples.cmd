@echo off
setlocal EnableExtensions

pushd "%~dp0" || exit /b 1
python tools\verify_stage3_compiler_on_examples.py
set "VERIFY_EXIT=%ERRORLEVEL%"
popd
exit /b %VERIFY_EXIT%
