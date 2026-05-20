@echo off
pushd "%~dp0..\..\.." >nul
python -m freehold test-language --module 05_records %*
set EXITCODE=%ERRORLEVEL%
popd >nul
exit /b %EXITCODE%