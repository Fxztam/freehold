@echo off
setlocal

pushd "%~dp0" || exit /b 1
python ".\tools\verify_spec_diagnostics.py" --diag ".\spec\freehold.diag" --rules ".\spec\freehold.rules" --expected-syntax ".\tests\language_modules\expected_diagnostics.json" --expected-semantic ".\tests\language_modules\expected_semantic_diagnostics.json" --out ".\artifacts\verify-spec-diagnostics"
set "exit_code=%errorlevel%"
popd
exit /b %exit_code%