@echo off
pushd "%~dp0..\..\.." >nul
python -m freehold test-language --module 04_types %*
set EXITCODE=%ERRORLEVEL%
popd >nul
exit /b %EXITCODE%