@echo off
pushd "%~dp0..\..\.." >nul
python -m freehold test-language --module 17_math_module %*
set EXITCODE=%ERRORLEVEL%
popd >nul
exit /b %EXITCODE%