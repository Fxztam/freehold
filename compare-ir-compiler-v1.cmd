@echo off
set PYTHON=python
if exist .\.venv\Scripts\python.exe set PYTHON=.\.venv\Scripts\python.exe
%PYTHON% .\tools\generate_compare_ir_samples.py --manifest .\artifacts\fhir-samples\compiler_v1\manifest.json --python-root .\artifacts\compare-ir\compiler_v1\python --go-root .\artifacts\compare-ir\compiler_v1\go
if errorlevel 1 exit /b %errorlevel%
%PYTHON% .\tools\compare_ir_hashes.py --manifest .\artifacts\fhir-samples\compiler_v1\manifest.json --python-root .\artifacts\compare-ir\compiler_v1\python --go-root .\artifacts\compare-ir\compiler_v1\go --out .\artifacts\compare-ir\compiler_v1\report