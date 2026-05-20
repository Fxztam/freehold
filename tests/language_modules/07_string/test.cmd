@echo off
pushd "%~dp0..\..\.." >nul
python -m freehold test-language --module 07_string %*
set EXITCODE=%ERRORLEVEL%
popd >nul
exit /b %EXITCODE%