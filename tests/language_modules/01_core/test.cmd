@echo off
pushd "%~dp0..\..\.." >nul
python -m freehold test-language --module 01_core %*
set EXITCODE=%ERRORLEVEL%
popd >nul
exit /b %EXITCODE%