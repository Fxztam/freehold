@echo off
pushd "%~dp0..\..\.." >nul
python -m freehold test-language --module 13_contract_blocks %*
set EXITCODE=%ERRORLEVEL%
popd >nul
exit /b %EXITCODE%