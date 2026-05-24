@echo off
setlocal

pushd "%~dp0" || exit /b 1
python ".\tools\verify_go_feature_matrix.py"
set "exit_code=%errorlevel%"
popd
exit /b %exit_code%