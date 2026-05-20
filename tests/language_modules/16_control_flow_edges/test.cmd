@echo off
pushd "%~dp0..\..\.." >nul
python -m freehold test-language --module 16_control_flow_edges %*
set EXITCODE=%ERRORLEVEL%
popd >nul
exit /b %EXITCODE%