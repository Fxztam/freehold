@echo off
set "PYTHONPATH=%~dp0;%PYTHONPATH%"
python "%~dp0tools\test_steps.py" %*