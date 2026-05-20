@echo off
pushd "%~dp0..\..\.." >nul
python -m freehold test-language --module 09_statements %*
set EXITCODE=%ERRORLEVEL%
popd >nul
exit /b %EXITCODE%