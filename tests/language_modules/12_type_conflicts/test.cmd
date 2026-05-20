@echo off
pushd "%~dp0..\..\.." >nul
python -m freehold test-language --module 12_type_conflicts %*
set EXITCODE=%ERRORLEVEL%
popd >nul
exit /b %EXITCODE%