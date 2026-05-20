@echo off
pushd "%~dp0..\..\.." >nul
python -m freehold test-language --module 06_arrays %*
set EXITCODE=%ERRORLEVEL%
popd >nul
exit /b %EXITCODE%