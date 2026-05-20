@echo off
pushd "%~dp0..\..\.." >nul
python -m freehold test-language --module 15_qualified_names_calls %*
set EXITCODE=%ERRORLEVEL%
popd >nul
exit /b %EXITCODE%