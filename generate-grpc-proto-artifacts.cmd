@echo off
setlocal

pushd "%~dp0" || exit /b 1
python ".\tools\generate_grpc_proto_artifacts.py" --additive
set "exit_code=%errorlevel%"
popd
exit /b %exit_code%
