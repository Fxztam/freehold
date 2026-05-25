@echo off
setlocal EnableExtensions

pushd "%~dp0" || exit /b 1
python tools\verify_compiler_examples.py
set "VERIFY_EXIT=%ERRORLEVEL%"
popd
exit /b %VERIFY_EXIT%