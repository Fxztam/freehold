@echo off
pushd "%~dp0..\..\.." >nul
python -m freehold test-language --module 10_expressions %*
set EXITCODE=%ERRORLEVEL%
popd >nul
exit /b %EXITCODE%